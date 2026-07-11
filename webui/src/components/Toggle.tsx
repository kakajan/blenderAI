import "./Toggle.css";

type Props = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  hint?: string;
  disabled?: boolean;
  /** compact = small switch without wide track feel */
  size?: "md" | "sm";
};

export default function Toggle({
  checked,
  onChange,
  label,
  hint,
  disabled = false,
  size = "md",
}: Props) {
  return (
    <label className={`ui-toggle ${size} ${checked ? "is-on" : ""} ${disabled ? "is-disabled" : ""}`}>
      <input
        type="checkbox"
        className="ui-toggle-input"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="ui-toggle-track" aria-hidden>
        <span className="ui-toggle-thumb">
          {checked ? (
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <path
                d="M2 5.2L4.1 7.2L8 2.8"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          ) : null}
        </span>
      </span>
      {(label || hint) && (
        <span className="ui-toggle-text">
          {label ? <span className="ui-toggle-label">{label}</span> : null}
          {hint ? <span className="ui-toggle-hint">{hint}</span> : null}
        </span>
      )}
    </label>
  );
}
