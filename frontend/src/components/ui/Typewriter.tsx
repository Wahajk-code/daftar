import styles from "./Typewriter.module.css";

/**
 * Text that types itself out once, with a caret that travels with the last letter and then blinks a few times and goes. It is
 * pure CSS (a stepped reveal), so the text is in the page from the first byte: assistive technology reads it whole, and with
 * reduced motion it simply appears.
 */
export function Typewriter({ text }: { text: string }) {
  const style = { "--n": Math.max(text.length, 1) } as React.CSSProperties;
  return (
    <span className={styles.typed} style={style}>
      <span className={styles.text}>{text}</span>
      <span className={styles.caret} aria-hidden />
    </span>
  );
}
