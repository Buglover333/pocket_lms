import React from 'react';

export function Icon({ name, size = 32, className = '' }) {
  const svgs = {
    person: (
      <>
        <circle cx="16" cy="11" r="6" />
        <path d="M5 29c0-7 4.5-11 11-11s11 4 11 11" />
      </>
    ),
    dash: (
      <>
        <path d="M4 18a12 12 0 0 1 24 0v5H4z" />
        <path d="m16 18 5-8" />
      </>
    ),
    book: (
      <>
        <rect x="6" y="3" width="21" height="26" rx="2" />
        <path d="M10 7h13v13H10zm0 17h13" />
      </>
    ),
    users: (
      <>
        <circle cx="11" cy="11" r="5" />
        <circle cx="23" cy="12" r="4" />
        <path d="M2 27c0-6 4-10 9-10s9 4 9 10M19 19c6-2 11 2 11 8H18" />
      </>
    ),
    calendar: (
      <>
        <rect x="4" y="6" width="24" height="23" rx="2" />
        <path d="M9 3v6m14-6v6M4 12h24" />
      </>
    ),
    gear: (
      <>
        <circle cx="16" cy="16" r="5" />
        <path d="M13 3h6l1 4 3 1 4-2 3 5-3 3v4l3 3-3 5-4-2-3 1-1 4h-6l-1-4-3-1-4 2-3-5 3-3v-4l-3-3 3-5 4 2 3-1z" />
      </>
    ),
    doc: (
      <>
        <path d="M7 3h12l6 6v20H7zM19 3v7h6M11 15h10m-10 5h10" />
      </>
    ),
    cover: (
      <>
        <path d="m4 10 12-6 12 6-12 6z" />
        <path d="M8 12v9c5 4 11 4 16 0v-9" />
      </>
    ),
    grades: (
      <>
        <path d="M6 4h20v24H6zM10 10h12M10 16h7m4-2 2 2 4-5" />
      </>
    ),
  };

  return (
    <svg
      viewBox="0 0 32 32"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {svgs[name] || svgs.dash}
    </svg>
  );
}
