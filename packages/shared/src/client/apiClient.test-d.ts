import { listContacts, ListContactsParams } from "./apiClient";

// Type-level verification test for listContacts argument order
export async function testListContactsOrder() {
  const params: ListContactsParams = { saved_only: true };

  // Valid order: (baseUrl, token, params) - must compile cleanly
  await listContacts("http://localhost:8000", "valid-token", params);

  // Valid order: (baseUrl, token) without params - must compile cleanly
  await listContacts("http://localhost:8000", "valid-token");

  // Invalid / old order: (baseUrl, params, token)
  // @ts-expect-error - Passing params as 2nd argument must fail compilation
  await listContacts("http://localhost:8000", params, "valid-token");
}
