/**
 * Глобальные константы фронтенда.
 *
 * `API_URL` берётся из переменной окружения Vite `VITE_API_URL`, чтобы адрес
 * backend можно было переопределять при деплое, не меняя код.
 *
 * `AS_OF_DATE` — фиксированная дата демо-среза для summary и агентов.
 */
export const API_URL: string =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

export const AGENTS_API_URL: string =
  import.meta.env.VITE_AGENTS_API_URL || "http://localhost:8010";

export const AS_OF_DATE = "2026-06-19";
