/**
 * Глобальные константы фронтенда.
 *
 * `API_URL` берётся из переменной окружения Vite `VITE_API_URL`, чтобы адрес
 * backend можно было переопределять при деплое, не меняя код.
 *
 * `AS_OF_DATE` — дата среза портфеля. Demo-данные подготовлены под эту дату,
 * поэтому значение вынесено в одно место, а не размазано по компонентам.
 */
export const API_URL: string =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

export const AS_OF_DATE = "2026-06-19";

export const DEFAULT_PROJECT_ID = "P001";
