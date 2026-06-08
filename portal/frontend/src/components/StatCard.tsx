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
import type { ReactNode } from 'react';

import styles from './StatCard.module.css';

interface StatCardProps {
  title: string;
  value: number | string;
  icon?: ReactNode;
  accent?: 'blue' | 'green' | 'amber' | 'slate';
  onClick?: () => void;
}

export function StatCard({
  title,
  value,
  icon,
  accent = 'blue',
  onClick,
}: StatCardProps) {
  const interactive = Boolean(onClick);

  return (
    <article
      className={`${styles.card} ${interactive ? styles.interactive : ''}`}
      onClick={onClick}
      onKeyDown={
        interactive
          ? (event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                onClick?.();
              }
            }
          : undefined
      }
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
    >
      <div className={styles.header}>
        <span className={styles.title}>{title}</span>
        {icon ? (
          <span className={`${styles.iconWrap} ${styles[accent]}`} aria-hidden>
            {icon}
          </span>
        ) : null}
      </div>
      <div className={styles.value}>{value}</div>
    </article>
  );
}
