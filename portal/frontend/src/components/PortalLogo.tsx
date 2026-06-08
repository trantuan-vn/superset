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
import { useId, type CSSProperties } from 'react';

import styles from './PortalLogo.module.css';

export type PortalLogoSize = 'sm' | 'md' | 'lg';

interface PortalLogoProps {
  size?: PortalLogoSize;
  className?: string;
  /** Override gradient start (tenant primary). */
  accentColor?: string;
  title?: string;
}

const SIZE_MAP: Record<PortalLogoSize, number> = {
  sm: 32,
  md: 40,
  lg: 56,
};

export function PortalLogo({
  size = 'md',
  className,
  accentColor,
  title = 'Portal Kết xuất',
}: PortalLogoProps) {
  const gradientId = useId();
  const dimension = SIZE_MAP[size];

  const style: CSSProperties | undefined = accentColor
    ? ({ '--portal-logo-accent': accentColor } as CSSProperties)
    : undefined;

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 48 48"
      fill="none"
      width={dimension}
      height={dimension}
      className={`${styles.logo} ${className ?? ''}`}
      style={style}
      role="img"
      aria-label={title}
    >
      <title>{title}</title>
      <defs>
        <linearGradient
          id={gradientId}
          x1="4"
          y1="4"
          x2="44"
          y2="44"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#1e3a8a" />
          <stop offset="1" stopColor={accentColor ?? '#2563eb'} />
        </linearGradient>
      </defs>
      <rect width="48" height="48" rx="12" fill={`url(#${gradientId})`} />
      <path
        d="M15 14h11.5l5.5 5.5V33a2 2 0 0 1-2 2H15a2 2 0 0 1-2-2V16a2 2 0 0 1 2-2Z"
        fill="#fff"
        fillOpacity="0.96"
      />
      <path d="M26.5 14v5.5H32" fill="#fff" fillOpacity="0.35" />
      <path
        d="M24 27.5v7M20.5 31l3.5 3.5L27.5 31"
        stroke="#fff"
        strokeWidth="2.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M18 22h12"
        stroke={accentColor ?? '#2563eb'}
        strokeWidth="1.75"
        strokeLinecap="round"
        opacity="0.55"
      />
      <path
        d="M18 25.5h8"
        stroke={accentColor ?? '#2563eb'}
        strokeWidth="1.75"
        strokeLinecap="round"
        opacity="0.4"
      />
    </svg>
  );
}
