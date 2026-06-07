/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

function pemToBytes(pem: string): Uint8Array {
  const base64 = pem
    .replace(/-----BEGIN[\s\S]+?-----/g, '')
    .replace(/-----END[\s\S]+?-----/g, '')
    .replace(/\s/g, '');
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i) ?? 0;
  }
  return bytes;
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i] ?? 0);
  }
  return btoa(binary);
}

function toArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  const copy = new Uint8Array(bytes.byteLength);
  copy.set(bytes);
  return copy.buffer;
}

function concatBytes(...parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((sum, part) => sum + part.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.length;
  }
  return out;
}

function readDerLength(
  data: Uint8Array,
  offset: number,
): { length: number; next: number } {
  const first = data[offset];
  if (first === undefined) {
    throw new Error('Invalid DER encoding');
  }
  if (first < 0x80) {
    return { length: first, next: offset + 1 };
  }
  const numBytes = first & 0x7f;
  let length = 0;
  for (let i = 1; i <= numBytes; i += 1) {
    length = (length << 8) | (data[offset + i] ?? 0);
  }
  return { length, next: offset + 1 + numBytes };
}

function readDerElement(
  data: Uint8Array,
  offset: number,
): { tag: number; content: Uint8Array; next: number } {
  const tag = data[offset];
  if (tag === undefined) {
    throw new Error('Invalid DER encoding');
  }
  const { length, next } = readDerLength(data, offset + 1);
  const content = data.slice(next, next + length);
  return { tag, content, next: next + length };
}

/** Extract inner SEC1 ECPrivateKey bytes from a PKCS#8 wrapper. */
function extractPkcs8Payload(pkcs8Der: Uint8Array): Uint8Array {
  const root = readDerElement(pkcs8Der, 0);
  if (root.tag !== 0x30) {
    throw new Error('Invalid PKCS#8 structure');
  }
  let cursor = 0;
  const version = readDerElement(root.content, cursor);
  cursor = version.next;
  const algorithm = readDerElement(root.content, cursor);
  cursor = algorithm.next;
  const privateKey = readDerElement(root.content, cursor);
  if (privateKey.tag !== 0x04) {
    throw new Error('Invalid PKCS#8 private key octet string');
  }
  return privateKey.content;
}

function pkcs8UsesEcAlgorithm(pkcs8Der: Uint8Array): boolean {
  const root = readDerElement(pkcs8Der, 0);
  if (root.tag !== 0x30) {
    return false;
  }
  let cursor = 0;
  const version = readDerElement(root.content, cursor);
  cursor = version.next;
  const algorithm = readDerElement(root.content, cursor);
  // id-ecPublicKey OID: 1.2.840.10045.2.1 -> 06 07 2a8648ce3d0201
  const ecOid = new Uint8Array([0x06, 0x07, 0x2a, 0x86, 0x48, 0xce, 0x3d, 0x02, 0x01]);
  if (algorithm.content.length < ecOid.length) {
    return false;
  }
  for (let i = 0; i < ecOid.length; i += 1) {
    if (algorithm.content[i] !== ecOid[i]) {
      return false;
    }
  }
  return true;
}

/** Wrap SEC1 ECPrivateKey DER as PKCS#8 for Web Crypto import. */
function wrapSec1AsPkcs8(sec1Der: Uint8Array): Uint8Array {
  const algorithmId = new Uint8Array([
    0x30, 0x13, 0x06, 0x07, 0x2a, 0x86, 0x48, 0xce, 0x3d, 0x02, 0x01, 0x06, 0x08,
    0x2a, 0x86, 0x48, 0xce, 0x3d, 0x03, 0x01, 0x07,
  ]);
  const version = new Uint8Array([0x02, 0x01, 0x00]);

  let octetHeader: Uint8Array;
  if (sec1Der.length < 128) {
    octetHeader = new Uint8Array([0x04, sec1Der.length]);
  } else {
    octetHeader = new Uint8Array([0x04, 0x81, sec1Der.length]);
  }
  const octetString = concatBytes(octetHeader, sec1Der);
  const inner = concatBytes(version, algorithmId, octetString);

  let sequenceHeader: Uint8Array;
  if (inner.length < 128) {
    sequenceHeader = new Uint8Array([0x30, inner.length]);
  } else if (inner.length < 256) {
    sequenceHeader = new Uint8Array([0x30, 0x81, inner.length]);
  } else {
    sequenceHeader = new Uint8Array([
      0x30,
      0x82,
      (inner.length >> 8) & 0xff,
      inner.length & 0xff,
    ]);
  }
  return concatBytes(sequenceHeader, inner);
}

async function signWithEcPrivateKey(
  nonce: string,
  privateKeyPem: string,
): Promise<string> {
  const der = pemToBytes(privateKeyPem);
  const sec1Der = privateKeyPem.includes('BEGIN PRIVATE KEY')
    ? extractPkcs8Payload(der)
    : der;
  const pkcs8 = wrapSec1AsPkcs8(sec1Der);

  const cryptoKey = await crypto.subtle.importKey(
    'pkcs8',
    toArrayBuffer(pkcs8),
    { name: 'ECDSA', namedCurve: 'P-256' },
    false,
    ['sign'],
  );
  const signature = await crypto.subtle.sign(
    { name: 'ECDSA', hash: 'SHA-256' },
    cryptoKey,
    new TextEncoder().encode(nonce),
  );
  return arrayBufferToBase64(signature);
}

async function signWithRsaPrivateKey(
  nonce: string,
  privateKeyPem: string,
): Promise<string> {
  const keyData = pemToBytes(privateKeyPem);
  const cryptoKey = await crypto.subtle.importKey(
    'pkcs8',
    toArrayBuffer(keyData),
    { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  const signature = await crypto.subtle.sign(
    'RSASSA-PKCS1-v1_5',
    cryptoKey,
    new TextEncoder().encode(nonce),
  );
  return arrayBufferToBase64(signature);
}

/** Sign a PKI challenge nonce with a PEM private key (EC Step CA or RSA PKCS#8). */
export async function signChallengeWithPrivateKey(
  nonce: string,
  privateKeyPem: string,
): Promise<string> {
  const pem = privateKeyPem.trim();
  if (pem.includes('EC PRIVATE KEY')) {
    try {
      return await signWithEcPrivateKey(nonce, pem);
    } catch (error) {
      const detail =
        error instanceof Error ? error.message : 'EC key import failed';
      throw new Error(`Cannot sign with EC private key: ${detail}`);
    }
  }
  if (pem.includes('BEGIN PRIVATE KEY')) {
    const der = pemToBytes(pem);
    if (pkcs8UsesEcAlgorithm(der)) {
      try {
        return await signWithEcPrivateKey(nonce, pem);
      } catch (error) {
        const detail =
          error instanceof Error ? error.message : 'EC key import failed';
        throw new Error(`Cannot sign with EC private key: ${detail}`);
      }
    }
    return signWithRsaPrivateKey(nonce, pem);
  }
  if (pem.includes('RSA PRIVATE KEY')) {
    throw new Error(
      'RSA PKCS#1 keys are not supported — convert to PKCS#8 or re-issue with Step CA (EC)',
    );
  }
  throw new Error('Unsupported private key format');
}

export async function readFileAsText(file: File): Promise<string> {
  return file.text();
}
