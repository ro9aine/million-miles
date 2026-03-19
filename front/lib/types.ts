export type Lang = "ja" | "en" | "ru";

export type FilterOption = {
  value: string;
  label: string;
};

export type AvailableFilters = {
  makes: FilterOption[];
  body_types: FilterOption[];
  fuel_types: FilterOption[];
  transmissions: FilterOption[];
  drive_types: FilterOption[];
  locations: FilterOption[];
  colors: FilterOption[];
};

export type CarListItem = {
  listing_id: string;
  url?: string | null;
  title?: string | null;
  make?: string | null;
  model?: string | null;
  location?: string | null;
  year?: number | null;
  mileage_km?: number | null;
  base_price_yen?: number | null;
  total_price_yen?: number | null;
  engine_volume_cc?: number | null;
  doors?: number | null;
  seats?: number | null;
  photos: string[];
  main_photo?: string | null;
  body_type?: string | null;
  fuel_type?: string | null;
  transmission?: string | null;
  drive_type?: string | null;
  color?: string | null;
  shop_name?: string | null;
};

export type CarListResponse = {
  items: CarListItem[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  available_filters: AvailableFilters;
};

export type CarDetailResponse = {
  item: Record<string, unknown>;
};

export type LoginResponse = {
  authenticated: boolean;
  expires_in: number;
};

export type SessionResponse = {
  authenticated: boolean;
  username: string;
};

export type SyncResponse = {
  queued: boolean;
  task_id: string;
};
