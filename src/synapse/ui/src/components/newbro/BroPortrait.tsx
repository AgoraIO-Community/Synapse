import type { BroCardModel } from "./types";

export function BroPortrait({
  bro,
  active = false,
  talking,
}: {
  bro: BroCardModel;
  active?: boolean;
  talking: boolean;
}) {
  const accent = active || talking;
  const stroke = accent ? "#b9fffb" : "#27d6d1";
  const muted = accent ? "rgba(185,255,251,0.72)" : "rgba(39,214,209,0.5)";
  const panelBg = accent
    ? "bg-[#062f33]/90 border-[#27d6d1]/35 shadow-[inset_0_1px_0_rgba(255,255,255,.14),0_14px_28px_rgba(0,0,0,.18)]"
    : "bg-[#062f33]/72 border-[#27d6d1]/25 shadow-[inset_0_1px_0_rgba(255,255,255,.12)]";

  return (
    <div
      className={`relative h-[68px] w-[68px] shrink-0 overflow-hidden rounded-[18px] border ${panelBg}`}
    >
      <div className="absolute inset-2 rounded-full border border-[#27d6d1]/18" />
      <div className="absolute -left-4 -top-5 h-16 w-16 rounded-full bg-[#27d6d1]/12 blur-xl" />
      <svg
        viewBox="0 0 68 68"
        className="relative h-full w-full"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        {bro.avatarType === "cat" && (
          <>
            <path
              d="M18 28 L24 18 L29 28"
              stroke={stroke}
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M39 28 L44 18 L50 28"
              stroke={stroke}
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <circle cx="34" cy="38" r="16" stroke={stroke} strokeWidth="2.2" />
            <circle cx="28" cy="37" r="1.5" fill={stroke} />
            <circle cx="40" cy="37" r="1.5" fill={stroke} />
            <path d="M31 44 Q34 46 37 44" stroke={stroke} strokeWidth="2" strokeLinecap="round" />
            <path d="M20 41 H11" stroke={muted} strokeWidth="1.6" strokeLinecap="round" />
            <path d="M20 45 H12" stroke={muted} strokeWidth="1.6" strokeLinecap="round" />
            <path d="M48 41 H57" stroke={muted} strokeWidth="1.6" strokeLinecap="round" />
            <path d="M48 45 H56" stroke={muted} strokeWidth="1.6" strokeLinecap="round" />
          </>
        )}

        {bro.avatarType === "bunny" && (
          <>
            <rect x="22" y="12" width="8" height="20" rx="4" stroke={stroke} strokeWidth="2.2" />
            <rect x="38" y="12" width="8" height="20" rx="4" stroke={stroke} strokeWidth="2.2" />
            <circle cx="34" cy="40" r="16" stroke={stroke} strokeWidth="2.2" />
            <circle cx="28" cy="38" r="1.5" fill={stroke} />
            <circle cx="40" cy="38" r="1.5" fill={stroke} />
            <path d="M31 45 Q34 47 37 45" stroke={stroke} strokeWidth="2" strokeLinecap="round" />
          </>
        )}

        {bro.avatarType === "fox" && (
          <>
            <path
              d="M19 30 L26 19 L31 31"
              stroke={stroke}
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M37 31 L42 19 L49 30"
              stroke={stroke}
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M18 39 Q18 24 34 24 Q50 24 50 39 Q50 54 34 54 Q18 54 18 39 Z"
              stroke={stroke}
              strokeWidth="2.2"
            />
            <circle cx="28" cy="38" r="1.5" fill={stroke} />
            <circle cx="40" cy="38" r="1.5" fill={stroke} />
            <path
              d="M30 45 L34 42 L38 45"
              stroke={stroke}
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </>
        )}

        {bro.avatarType === "bro" && (
          <>
            <circle cx="34" cy="30" r="11" stroke={stroke} strokeWidth="2.2" />
            <path d="M24 29 Q34 19 44 29" stroke={stroke} strokeWidth="2.2" strokeLinecap="round" />
            <circle cx="30" cy="31" r="1.4" fill={stroke} />
            <circle cx="38" cy="31" r="1.4" fill={stroke} />
            <path d="M31 36 Q34 38 37 36" stroke={stroke} strokeWidth="2" strokeLinecap="round" />
            <path
              d="M19 66 Q22 52 34 52 Q46 52 49 66"
              stroke={stroke}
              strokeWidth="2.2"
              strokeLinecap="round"
            />
          </>
        )}
      </svg>

      <div
        className={`absolute right-2 top-2 h-2.5 w-2.5 rounded-full ring-2 ${
          accent ? "ring-[rgba(255,255,255,0.92)]" : "ring-white"
        } ${bro.status === "busy" ? "bg-[#27d6d1] shadow-[0_0_10px_rgba(39,214,209,.8)]" : "bg-[#27d6d1]/55"}`}
      />
    </div>
  );
}
