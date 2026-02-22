import type { AxiosRequestConfig } from "axios";
import api from "./client";

export async function getData<T>(url: string, config?: AxiosRequestConfig) {
  const res = await api.get<T>(url, config);
  return res.data;
}

export async function postData<TResponse, TBody = unknown>(
  url: string,
  body?: TBody,
  config?: AxiosRequestConfig<TBody>,
) {
  const res = await api.post<TResponse>(url, body, config);
  return res.data;
}

export async function putData<TResponse, TBody = unknown>(
  url: string,
  body?: TBody,
  config?: AxiosRequestConfig<TBody>,
) {
  const res = await api.put<TResponse>(url, body, config);
  return res.data;
}

export async function deleteData<TResponse>(url: string, config?: AxiosRequestConfig) {
  const res = await api.delete<TResponse>(url, config);
  return res.data;
}
