export function buildProfilePayload(formValues, fields) {
  return Object.fromEntries(Object.entries(formValues).map(([key, value]) => {
    const field = fields.find((item) => item[0] === key);
    const normalized = value === '' ? null : field?.[2] === 'number' ? Number(value) : field?.[2] === 'boolean' ? value === 'true' : value;
    return [key, normalized];
  }));
}
