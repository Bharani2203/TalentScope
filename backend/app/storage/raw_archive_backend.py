"""Provider-neutral storage contract and Firestore raw-archive backend."""

from __future__ import annotations

from typing import Any, Protocol

from app.core.firebase import get_firestore_client


class RawArchiveBackend(Protocol):
    def write_complete(self, archive_id: str, metadata: dict[str, Any], payload: bytes) -> None: ...

    def read_complete(self, archive_id: str) -> tuple[dict[str, Any], bytes]: ...

    def delete(self, archive_id: str) -> None: ...


class RawArchiveError(RuntimeError):
    """Safe archive backend error that never includes provider or credential data."""


class ArchiveConflictError(RawArchiveError):
    """A deterministic archive ID is already bound to different archive data."""


class FirestoreRawArchiveBackend:
    collection_name = "raw_response_archives"
    chunk_size = 256 * 1024
    # 32 x 256 KiB is at most 8 MiB of payload per Commit request, below Firestore's 10 MiB limit.
    write_batch_size = 32

    def __init__(self, client: Any | None = None):
        self.client = client

    def _collection(self):
        return (self.client or get_firestore_client()).collection(self.collection_name)

    @staticmethod
    def _identity_fields() -> tuple[str, ...]:
        return (
            "archive_id", "fetch_run_id", "source", "provider", "content_type",
            "encoding", "checksum", "size_bytes", "chunk_count", "response_index",
            "archive_reference", "retention_class", "collected_at",
        )

    def write_complete(self, archive_id: str, metadata: dict[str, Any], payload: bytes) -> None:
        collection = self._collection()
        metadata_ref = collection.document(archive_id)
        expected = {**metadata, "archive_id": archive_id}
        snapshot = metadata_ref.get()

        if getattr(snapshot, "exists", False):
            existing = snapshot.to_dict() or {}
            if any(existing.get(key) != expected.get(key) for key in self._identity_fields()):
                raise ArchiveConflictError("Conflicting raw response archive already exists.")
            if existing.get("status") == "complete":
                verified_metadata, verified_payload = self.read_complete(archive_id)
                if verified_metadata.get("checksum") != expected.get("checksum") or verified_payload != payload:
                    raise ArchiveConflictError("Conflicting raw response archive already exists.")
                return
            if existing.get("status") != "writing":
                raise ArchiveConflictError("Raw response archive has an invalid write state.")
            metadata_ref.update({"status": "writing", "last_error": None})
        else:
            metadata_ref.create({**expected, "status": "writing", "last_error": None})

        try:
            chunk_collection = metadata_ref.collection("chunks")
            chunks = [payload[offset:offset + self.chunk_size]
                      for offset in range(0, len(payload), self.chunk_size)]

            # A retry may find chunks from an interrupted write. Keep matching chunks,
            # replace missing ones, and remove only extra children of this archive.
            existing_chunks = {doc.id: doc for doc in chunk_collection.stream()}
            expected_ids = {f"{index:08d}" for index in range(len(chunks))}
            stale_refs = [doc.reference for doc_id, doc in existing_chunks.items() if doc_id not in expected_ids]
            self._delete_refs(stale_refs)

            client = self.client or get_firestore_client()
            for offset in range(0, len(chunks), self.write_batch_size):
                batch = client.batch()
                for index in range(offset, min(offset + self.write_batch_size, len(chunks))):
                    chunk_id = f"{index:08d}"
                    chunk_ref = chunk_collection.document(chunk_id)
                    chunk = chunks[index]
                    prior = existing_chunks.get(chunk_id)
                    if prior is not None:
                        prior_data = prior.to_dict() or {}
                        if prior_data.get("index") != index or prior_data.get("payload_bytes") != chunk:
                            raise ArchiveConflictError("Conflicting raw response archive chunk exists.")
                        continue
                    batch.set(chunk_ref, {
                        "index": index,
                        "payload_bytes": chunk,
                        "checksum": _sha256(chunk),
                    })
                # Empty batches are invalid; matching chunks need no rewrite.
                if any(f"{index:08d}" not in existing_chunks
                       for index in range(offset, min(offset + self.write_batch_size, len(chunks)))):
                    batch.commit()

            stored_chunks = list(chunk_collection.stream())
            if len(stored_chunks) != len(chunks):
                raise RawArchiveError("Raw response archive chunk count verification failed.")
            reconstructed = self._reconstruct_chunks(stored_chunks, len(chunks))
            if len(reconstructed) != expected["size_bytes"]:
                raise RawArchiveError("Raw response archive size verification failed.")
            if _sha256(reconstructed) != expected["checksum"] or reconstructed != payload:
                raise RawArchiveError("Raw response archive checksum verification failed.")
            metadata_ref.update({"status": "complete", "last_error": None})
        except ArchiveConflictError:
            raise
        except Exception:
            try:
                metadata_ref.update({"status": "writing", "last_error": "archive_write_failed"})
            except Exception:
                pass
            raise RawArchiveError("Provider response archive could not be stored.") from None

    def read_complete(self, archive_id: str) -> tuple[dict[str, Any], bytes]:
        metadata_ref = self._collection().document(archive_id)
        snapshot = metadata_ref.get()
        if not getattr(snapshot, "exists", False):
            raise RawArchiveError("Raw response archive was not found.")
        metadata = snapshot.to_dict() or {}
        if metadata.get("archive_id") != archive_id:
            raise RawArchiveError("Raw response archive identity verification failed.")
        if metadata.get("status") != "complete":
            raise RawArchiveError("Raw response archive is incomplete.")
        chunk_count = metadata.get("chunk_count")
        if not isinstance(chunk_count, int) or isinstance(chunk_count, bool) or chunk_count < 1:
            raise RawArchiveError("Raw response archive metadata is invalid.")
        chunks = list(metadata_ref.collection("chunks").stream())
        payload = self._reconstruct_chunks(chunks, chunk_count)
        if len(payload) != metadata.get("size_bytes"):
            raise RawArchiveError("Raw response archive size verification failed.")
        if _sha256(payload) != metadata.get("checksum"):
            raise RawArchiveError("Raw response archive checksum verification failed.")
        return metadata, payload

    def delete(self, archive_id: str) -> None:
        metadata_ref = self._collection().document(archive_id)
        snapshot = metadata_ref.get()
        if not getattr(snapshot, "exists", False):
            return
        metadata = snapshot.to_dict() or {}
        if metadata.get("archive_id") != archive_id:
            raise RawArchiveError("Raw response archive identity verification failed.")
        self._delete_refs([doc.reference for doc in metadata_ref.collection("chunks").stream()])
        metadata_ref.delete()

    def _delete_refs(self, references: list[Any]) -> None:
        if not references:
            return
        client = self.client or get_firestore_client()
        for offset in range(0, len(references), self.write_batch_size):
            batch = client.batch()
            for reference in references[offset:offset + self.write_batch_size]:
                batch.delete(reference)
            batch.commit()

    @staticmethod
    def _reconstruct_chunks(documents: list[Any], expected_count: int) -> bytes:
        if len(documents) != expected_count:
            raise RawArchiveError("Raw response archive chunk count verification failed.")
        indexed: dict[int, bytes] = {}
        for document in documents:
            data = document.to_dict() or {}
            index = data.get("index")
            chunk = data.get("payload_bytes")
            if not isinstance(index, int) or isinstance(index, bool) or not isinstance(chunk, bytes):
                raise RawArchiveError("Raw response archive chunk is invalid.")
            if index in indexed or index < 0 or index >= expected_count:
                raise RawArchiveError("Raw response archive chunk index verification failed.")
            if data.get("checksum") != _sha256(chunk):
                raise RawArchiveError("Raw response archive chunk checksum verification failed.")
            indexed[index] = chunk
        if set(indexed) != set(range(expected_count)):
            raise RawArchiveError("Raw response archive chunk index verification failed.")
        return b"".join(indexed[index] for index in range(expected_count))


def _sha256(payload: bytes) -> str:
    import hashlib

    return hashlib.sha256(payload).hexdigest()
