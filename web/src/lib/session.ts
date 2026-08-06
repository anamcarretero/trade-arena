import {cookies} from "next/headers";
import {EncryptJWT, jwtDecrypt} from "jose";
import type {Locale} from "./i18n";
import {cookiePolicy} from "./cookie-policy";

export type LoginTransaction = {
  state: string;
  nonce: string;
  codeVerifier: string;
  returnTo: string;
  locale: "es" | "en";
};

function policy() {
  return cookiePolicy(process.env.APP_BASE_URL);
}

function encryptionKey(): Uint8Array {
  const raw = process.env.SESSION_ENCRYPTION_KEY;
  if (!raw) throw new Error("SESSION_ENCRYPTION_KEY is required");
  const key = Buffer.from(raw, "base64url");
  if (key.length !== 32) throw new Error("SESSION_ENCRYPTION_KEY must be 32 base64url bytes");
  return key;
}

async function seal(payload: object, expiresIn: string) {
  return new EncryptJWT({...payload})
    .setProtectedHeader({alg: "dir", enc: "A256GCM"})
    .setIssuedAt()
    .setExpirationTime(expiresIn)
    .encrypt(encryptionKey());
}

async function unseal<T>(value: string): Promise<T | null> {
  try {
    const {payload} = await jwtDecrypt(value, encryptionKey(), {
      keyManagementAlgorithms: ["dir"],
      contentEncryptionAlgorithms: ["A256GCM"]
    });
    return payload as T;
  } catch {
    return null;
  }
}

export async function saveTransaction(transaction: LoginTransaction) {
  const jar = await cookies();
  const current = policy();
  jar.set(current.transactionName, await seal(transaction, "10m"), {
    httpOnly: true, secure: current.secure, sameSite: "lax", path: "/", maxAge: 600
  });
}

export async function consumeTransaction() {
  const jar = await cookies();
  const name = policy().transactionName;
  const value = jar.get(name)?.value;
  jar.delete(name);
  return value ? unseal<LoginTransaction>(value) : null;
}

export async function saveSession(token: string, maxAge: number) {
  const jar = await cookies();
  const current = policy();
  jar.set(current.sessionName, await seal({token}, `${maxAge}s`), {
    httpOnly: true, secure: current.secure, sameSite: "lax", path: "/", maxAge
  });
}

export async function readSessionToken() {
  const value = (await cookies()).get(policy().sessionName)?.value;
  const session = value ? await unseal<{token?: string}>(value) : null;
  return session?.token ?? null;
}

export async function clearSession() {
  (await cookies()).delete(policy().sessionName);
}

export async function saveLocale(locale: Locale) {
  (await cookies()).set("tradearena_locale", locale, {
    httpOnly: true, secure: policy().secure, sameSite: "lax", path: "/",
    maxAge: 60 * 60 * 24 * 365
  });
}
