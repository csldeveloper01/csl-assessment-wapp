/**
 * Safe, human-readable API and runtime error message extractor.
 * Guaranteed to return a non-empty string. Never returns an object, null, or undefined.
 *
 * Handles:
 * - Simple string errors
 * - Axios errors with structured response.data
 * - Objects with { bank_error: ... }
 * - Objects with { detail: string | object }
 * - Django REST Framework field validation errors: { field: ["Error 1", "Error 2"] }
 * - Arrays of error strings / objects
 * - Native JS Error objects
 * - Unknown / empty / null / undefined values
 */
export function formatApiError(err: unknown, defaultMessage = 'An unexpected error occurred.'): string {
  if (!err) {
    return defaultMessage;
  }

  // 1. Primitive string
  if (typeof err === 'string') {
    const trimmed = err.trim();
    return trimmed.length > 0 ? trimmed : defaultMessage;
  }

  // 2. Array of errors
  if (Array.isArray(err)) {
    const formattedItems = err
      .map((item) => formatApiError(item, ''))
      .filter((s) => s.length > 0);
    return formattedItems.length > 0 ? formattedItems.join('; ') : defaultMessage;
  }

  // 3. Object inspection
  if (typeof err === 'object') {
    // If Axios-like response is present
    const axErr = err as {
      response?: {
        data?: unknown;
        status?: number;
        statusText?: string;
      };
      message?: string;
    };

    if (axErr.response && axErr.response.data !== undefined && axErr.response.data !== null) {
      return formatApiError(axErr.response.data, axErr.message || defaultMessage);
    }

    const obj = err as Record<string, unknown>;

    // Handle dedicated bank_error directly
    if (obj.bank_error !== undefined && obj.bank_error !== null) {
      return formatApiError(obj.bank_error, defaultMessage);
    }

    // Handle detail field (string, array, or nested object)
    if (obj.detail !== undefined && obj.detail !== null) {
      return formatApiError(obj.detail, defaultMessage);
    }

    // Handle general message or error fields
    if (typeof obj.message === 'string' && obj.message.trim()) {
      return obj.message.trim();
    }
    if (typeof obj.error === 'string' && obj.error.trim()) {
      return obj.error.trim();
    }

    // Handle dictionary of field errors (e.g. { code: ["Taken"], sections: "Invalid" })
    const entries = Object.entries(obj).filter(([_, val]) => val !== undefined && val !== null);
    if (entries.length > 0) {
      const fieldMessages = entries.map(([key, val]) => {
        let formattedVal = '';
        if (typeof val === 'string') {
          formattedVal = val;
        } else if (Array.isArray(val)) {
          formattedVal = val
            .map((v) => (typeof v === 'string' ? v : formatApiError(v, '')))
            .filter((v) => v.length > 0)
            .join(', ');
        } else if (typeof val === 'object') {
          formattedVal = formatApiError(val, '');
        } else {
          formattedVal = String(val);
        }

        if (key.toLowerCase() === 'bank_error' || key.toLowerCase() === 'non_field_errors') {
          return formattedVal;
        }

        const readableKey = key
          .replace(/_/g, ' ')
          .replace(/\b\w/g, (char) => char.toUpperCase());

        return `${readableKey}: ${formattedVal}`;
      });

      const joined = fieldMessages.filter((msg) => msg.trim().length > 0).join('; ');
      if (joined.length > 0) {
        return joined;
      }
    }

    if (err instanceof Error && err.message) {
      return err.message;
    }
  }

  return defaultMessage;
}
