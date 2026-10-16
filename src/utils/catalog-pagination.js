export const CATALOG_PAGE_SIZE = 10;

export function paginateCatalog(items, requestedPage, pageSize = CATALOG_PAGE_SIZE) {
  const records = Array.isArray(items) ? items : [];
  const size = Math.max(1, Math.floor(Number(pageSize) || CATALOG_PAGE_SIZE));
  const total = records.length;
  const pageCount = Math.max(1, Math.ceil(total / size));
  const page = Math.min(pageCount, Math.max(1, Math.floor(Number(requestedPage) || 1)));
  const startIndex = total ? (page - 1) * size : 0;
  const endIndex = Math.min(total, startIndex + size);
  return {
    items: records.slice(startIndex, endIndex),
    page,
    pageCount,
    total,
    start: total ? startIndex + 1 : 0,
    end: endIndex
  };
}
