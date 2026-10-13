import styles from "./LedgerArt.module.css";

/**
 * The login page's picture: two flat, long-limbed people at a giant open ledger, in the style of hand-built character
 * illustration (thick rounded limbs, no outlines). One draws an entry with an oversized pen, the other holds up a checked
 * sheet; coins, a receipt and a stack of vouchers float between them. Every colour is a design token (skin tones included),
 * so it follows the light and dark theme. It is decoration: hidden from assistive technology.
 */
export function LedgerArt() {
  return (
    <svg className={styles.art} viewBox="0 0 640 720" role="presentation" aria-hidden focusable="false">
      {/* A soft stage behind everything. */}
      <circle className={styles.stage} cx="320" cy="340" r="236" />
      <circle className={styles.dotA} cx="86" cy="150" r="9" />
      <circle className={styles.dotB} cx="566" cy="118" r="13" />
      <circle className={styles.dotC} cx="540" cy="520" r="7" />

      {/* Rising bars behind the book. */}
      <g className={styles.bars}>
        <rect x="372" y="388" width="34" height="96" rx="8" fill="var(--chart-2)" />
        <rect x="414" y="332" width="34" height="152" rx="8" fill="var(--chart-1)" />
        <rect x="456" y="368" width="34" height="116" rx="8" fill="var(--caution)" />
      </g>

      {/* Floating paper and coins. */}
      <g className={`${styles.float} ${styles.slow}`}>
        <g transform="rotate(-8 255 205)">
          <rect x="212" y="170" width="92" height="62" rx="10" fill="var(--bg-raised)" stroke="var(--rule-strong)" strokeWidth="2" />
          <rect x="222" y="184" width="48" height="7" rx="3.5" fill="var(--text-3)" />
          <rect x="222" y="200" width="70" height="7" rx="3.5" fill="var(--rule-strong)" />
          <rect x="222" y="214" width="34" height="7" rx="3.5" fill="var(--rule-strong)" />
        </g>
      </g>
      <g className={styles.float}>
        <path d="M298 262h74v96l-9.25-8-9.25 8-9.25-8-9.25 8-9.25-8-9.25 8-9.25-8z" fill="var(--bg-raised)" stroke="var(--rule-strong)" strokeWidth="2" strokeLinejoin="round" />
        <rect x="310" y="278" width="40" height="7" rx="3.5" fill="var(--text-3)" />
        <rect x="310" y="294" width="50" height="7" rx="3.5" fill="var(--rule-strong)" />
        <rect x="310" y="310" width="30" height="7" rx="3.5" fill="var(--rule-strong)" />
        <rect x="336" y="328" width="24" height="9" rx="4.5" fill="var(--chart-1)" />
      </g>
      <g className={`${styles.float} ${styles.fast}`}>
        <circle cx="402" cy="236" r="19" fill="var(--caution)" />
        <circle cx="402" cy="236" r="11.5" fill="none" stroke="var(--bg-surface)" strokeWidth="2.5" />
        <circle cx="236" cy="316" r="14" fill="var(--caution)" />
        <circle cx="236" cy="316" r="8" fill="none" stroke="var(--bg-surface)" strokeWidth="2.5" />
      </g>
      <g className={`${styles.float} ${styles.slow}`}>
        <circle cx="452" cy="262" r="28" fill="var(--positive)" />
        <path d="M439 262l9 9 17-19" fill="none" stroke="var(--bg-surface)" strokeWidth="5.5" strokeLinecap="round" strokeLinejoin="round" />
      </g>

      {/* The open ledger: a dark cover, two pages ruled with a debit and a credit column. */}
      <g>
        <rect x="84" y="488" width="472" height="158" rx="22" fill="var(--text-1)" />
        <rect x="100" y="470" width="214" height="158" rx="14" fill="var(--bg-raised)" />
        <rect x="326" y="470" width="214" height="158" rx="14" fill="var(--bg-raised)" />
        <rect x="312" y="466" width="16" height="170" rx="6" fill="var(--text-2)" />
        <rect x="244" y="470" width="70" height="26" fill="var(--debit-wash)" />
        <rect x="326" y="470" width="70" height="26" fill="var(--credit-wash)" />
        {[516, 538, 560, 582, 604].map((y) => (
          <g key={y}>
            <line x1="100" y1={y} x2="314" y2={y} stroke="var(--rule-strong)" strokeWidth="1.5" />
            <line x1="326" y1={y} x2="540" y2={y} stroke="var(--rule-strong)" strokeWidth="1.5" />
          </g>
        ))}
        <line x1="244" y1="470" x2="244" y2="628" stroke="var(--rule-strong)" strokeWidth="1.5" />
        <line x1="396" y1="470" x2="396" y2="628" stroke="var(--rule-strong)" strokeWidth="1.5" />
        {[
          [112, 504, 92],
          [112, 526, 64],
          [112, 548, 110],
          [112, 570, 78],
          [112, 592, 100],
          [338, 504, 40],
          [338, 526, 70],
          [338, 548, 52],
          [338, 570, 86],
          [338, 592, 60],
        ].map(([x, y, w]) => (
          <rect key={`${x}-${y}`} x={x} y={y - 3} width={w} height="6" rx="3" fill="var(--text-3)" opacity="0.55" />
        ))}
        {[
          [254, 526, 46],
          [254, 570, 38],
          [404, 504, 54],
          [404, 548, 40],
          [404, 592, 62],
        ].map(([x, y, w]) => (
          <rect key={`n-${x}-${y}`} x={x} y={y - 3.5} width={w} height="7" rx="3.5" fill="var(--text-1)" opacity="0.8" />
        ))}
      </g>

      {/* The person at the left, writing an entry with an oversized pen. */}
      <g className={styles.personA}>
        <path d="M108 452 L96 630" stroke="var(--text-1)" strokeWidth="26" strokeLinecap="round" />
        <path d="M136 452 L150 630" stroke="var(--text-1)" strokeWidth="26" strokeLinecap="round" />
        <ellipse cx="90" cy="640" rx="24" ry="9" fill="var(--text-2)" />
        <ellipse cx="158" cy="640" rx="24" ry="9" fill="var(--text-2)" />
        <path d="M86 354 L66 424" stroke="var(--chart-1)" strokeWidth="24" strokeLinecap="round" />
        <circle cx="64" cy="436" r="12" fill="var(--art-skin-2)" />
        <rect x="80" y="330" width="84" height="140" rx="34" fill="var(--chart-1)" />
        <path d="M152 352 L196 402" stroke="var(--chart-1)" strokeWidth="24" strokeLinecap="round" />
        <path d="M196 402 L232 458" stroke="var(--art-skin-2)" strokeWidth="20" strokeLinecap="round" />
        <g transform="rotate(38 240 440)">
          <rect x="232" y="366" width="16" height="120" rx="8" fill="var(--caution)" />
          <path d="M232 486 L240 510 L248 486Z" fill="var(--text-1)" />
          <rect x="232" y="366" width="16" height="22" rx="8" fill="var(--text-1)" />
        </g>
        <rect x="112" y="304" width="18" height="34" rx="8" fill="var(--art-skin-2)" />
        <circle cx="121" cy="286" r="31" fill="var(--art-skin-2)" />
        <path d="M88 292 C84 258 108 246 126 249 C148 252 158 270 154 294 C142 276 130 270 112 274 C102 276 94 282 88 292Z" fill="var(--text-1)" />
      </g>

      {/* The person at the right, holding up a checked sheet. */}
      <g className={styles.personB}>
        <path d="M512 452 L504 630" stroke="var(--text-2)" strokeWidth="26" strokeLinecap="round" />
        <path d="M540 452 L552 630" stroke="var(--text-2)" strokeWidth="26" strokeLinecap="round" />
        <ellipse cx="496" cy="640" rx="24" ry="9" fill="var(--text-1)" />
        <ellipse cx="560" cy="640" rx="24" ry="9" fill="var(--text-1)" />
        <path d="M560 356 L580 422" stroke="var(--info)" strokeWidth="24" strokeLinecap="round" />
        <circle cx="582" cy="434" r="12" fill="var(--art-skin-3)" />
        <rect x="486" y="330" width="86" height="140" rx="34" fill="var(--info)" />
        <path d="M496 356 L458 392 L470 340" stroke="var(--info)" strokeWidth="24" strokeLinecap="round" strokeLinejoin="round" fill="none" />
        <circle cx="468" cy="336" r="12" fill="var(--art-skin-3)" />
        <g transform="rotate(-9 456 300)">
          <rect x="420" y="236" width="76" height="98" rx="12" fill="var(--bg-raised)" stroke="var(--rule-strong)" strokeWidth="2" />
          <rect x="446" y="228" width="24" height="14" rx="5" fill="var(--text-1)" />
          <rect x="432" y="258" width="40" height="6" rx="3" fill="var(--text-3)" />
          <rect x="432" y="274" width="52" height="6" rx="3" fill="var(--rule-strong)" />
          <path d="M434 302l9 9 18-20" fill="none" stroke="var(--positive)" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
        </g>
        <rect x="520" y="304" width="18" height="34" rx="8" fill="var(--art-skin-3)" />
        <circle cx="529" cy="286" r="31" fill="var(--art-skin-3)" />
        <path d="M496 292 C486 252 512 240 532 242 C556 244 570 266 562 300 C560 332 566 346 576 360 C556 354 548 332 546 306 C530 290 508 290 496 292Z" fill="var(--text-1)" />
      </g>

      {/* Plants and the ground. */}
      <g>
        <ellipse cx="36" cy="618" rx="14" ry="34" transform="rotate(-18 36 618)" fill="var(--chart-1)" />
        <ellipse cx="62" cy="624" rx="12" ry="28" transform="rotate(16 62 624)" fill="var(--positive)" opacity="0.7" />
        <rect x="22" y="630" width="52" height="30" rx="10" fill="var(--text-2)" />
        <ellipse cx="604" cy="612" rx="13" ry="32" transform="rotate(20 604 612)" fill="var(--positive)" opacity="0.7" />
        <ellipse cx="582" cy="620" rx="12" ry="28" transform="rotate(-14 582 620)" fill="var(--chart-1)" />
        <rect x="570" y="630" width="46" height="30" rx="10" fill="var(--text-2)" />
        <line x1="0" y1="660" x2="640" y2="660" stroke="var(--rule-strong)" strokeWidth="2" />
      </g>
    </svg>
  );
}
