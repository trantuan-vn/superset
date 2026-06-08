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

import styles from './PageHeader.module.css';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  breadcrumb?: { title: string; href?: string }[];
  extra?: ReactNode;
}

export function PageHeader({ title, subtitle, breadcrumb, extra }: PageHeaderProps) {
  return (
    <header className={styles.header}>
      {breadcrumb && breadcrumb.length > 0 ? (
        <nav className={styles.breadcrumb} aria-label="Breadcrumb">
          {breadcrumb.map((item, index) => (
            <span key={`${item.title}-${index}`} className={styles.breadcrumbItem}>
              {index > 0 ? <span className={styles.breadcrumbSep}>/</span> : null}
              {item.href ? (
                <a href={item.href} className={styles.breadcrumbLink}>
                  {item.title}
                </a>
              ) : (
                <span className={styles.breadcrumbCurrent}>{item.title}</span>
              )}
            </span>
          ))}
        </nav>
      ) : null}
      <div className={styles.row}>
        <div className={styles.textBlock}>
          <h1 className={styles.title}>{title}</h1>
          {subtitle ? <p className={styles.subtitle}>{subtitle}</p> : null}
        </div>
        {extra ? <div className={styles.extra}>{extra}</div> : null}
      </div>
    </header>
  );
}
