import axios from "axios";

type HttpMethod = "GET" | "POST";

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

type ApiRequestOptions = {
  method?: HttpMethod;
  body?: unknown;
  params?: Record<string, string | number | undefined | null>;
};

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  try {
    const response = await axios.request<T>({
      url: `${apiBaseUrl}${path}`,
      method: options.method ?? "GET",
      data: options.body,
      params: options.params,
      withCredentials: true,
      headers: {
        "Content-Type": "application/json",
      },
    });
    return response.data;
  } catch (error: unknown) {
    if (axios.isAxiosError(error)) {
      const status = error.response?.status ?? 0;
      const data = error.response?.data;
      const message =
        typeof data === "string"
          ? data
          : typeof data?.detail === "string"
            ? data.detail
            : error.message || `HTTP ${status}`;
      throw new ApiError(status, message);
    }
    throw error;
  }
}

export { apiBaseUrl };
