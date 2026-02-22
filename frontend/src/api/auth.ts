import { endpoints } from "./endpoints";
import { postData } from "./http";

export type LoginRequest = {
  email: string;
  password: string;
};

export type LoginResponse = {
  access_token: string;
};

export async function loginRequest(body: LoginRequest) {
  return postData<LoginResponse, LoginRequest>(endpoints.auth.login, body);
}
