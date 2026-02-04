import type { AxiosResponse } from "axios";
import api from "./client";
import { endpoints } from "./endpoints";

export type LoginRequest = {
  email: string;
  password: string;
};

export type LoginResponse = {
  access_token: string;
};

export async function loginRequest(body: LoginRequest) {
  const res = await api.post<LoginResponse, AxiosResponse<LoginResponse>, LoginRequest>(
    endpoints.auth.login,
    body
  );
  return res.data;
}
