import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import "./Select.css";

export type SelectOption = { value: string; label: string };

type Props = {
  label?: string;
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
};

type MenuPos = { top: number; left: number; width: number; maxHeight: number; openUp: boolean };

export default function Select({
  label,
  value,
  options,
  onChange,
  placeholder = "Select…",
  className = "",
  disabled = false,
}: Props) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<MenuPos | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLUListElement>(null);
  const listId = useId();
  const selected = options.find((o) => o.value === value);

  function updatePosition() {
    const el = triggerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const gap = 6;
    const preferredMax = 260;
    const spaceBelow = window.innerHeight - rect.bottom - gap - 8;
    const spaceAbove = rect.top - gap - 8;
    const openUp = spaceBelow < 140 && spaceAbove > spaceBelow;
    const maxHeight = Math.max(120, Math.min(preferredMax, openUp ? spaceAbove : spaceBelow));
    setPos({
      top: openUp ? rect.top - gap : rect.bottom + gap,
      left: rect.left,
      width: rect.width,
      maxHeight,
      openUp,
    });
  }

  useLayoutEffect(() => {
    if (!open) {
      setPos(null);
      return;
    }
    updatePosition();
    const onReposition = () => updatePosition();
    window.addEventListener("resize", onReposition);
    window.addEventListener("scroll", onReposition, true);
    return () => {
      window.removeEventListener("resize", onReposition);
      window.removeEventListener("scroll", onReposition, true);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      const t = e.target as Node;
      if (rootRef.current?.contains(t) || menuRef.current?.contains(t)) return;
      setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const menu =
    open && pos
      ? createPortal(
          <ul
            ref={menuRef}
            className={`ui-select-menu ${pos.openUp ? "opens-up" : "opens-down"}`}
            role="listbox"
            id={listId}
              style={{
              top: pos.openUp ? undefined : `${pos.top}px`,
              bottom: pos.openUp ? `${window.innerHeight - pos.top}px` : undefined,
              left: `${pos.left}px`,
              width: `${pos.width}px`,
              maxHeight: `${pos.maxHeight}px`,
            }}
          >
            {options.length === 0 && <li className="ui-select-empty">No options</li>}
            {options.map((opt) => {
              const active = opt.value === value;
              return (
                <li key={opt.value} role="option" aria-selected={active}>
                  <button
                    type="button"
                    className={`ui-select-option ${active ? "is-active" : ""}`}
                    onClick={() => {
                      onChange(opt.value);
                      setOpen(false);
                    }}
                  >
                    {opt.label}
                  </button>
                </li>
              );
            })}
          </ul>,
          document.body
        )
      : null;

  return (
    <div className={`ui-field ${open ? "is-open" : ""} ${className}`} ref={rootRef}>
      {label ? <span className="ui-label">{label}</span> : null}
      <button
        ref={triggerRef}
        type="button"
        className={`ui-select ${open ? "is-open" : ""}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        disabled={disabled}
        onClick={() => !disabled && setOpen((v) => !v)}
      >
        <span className={`ui-select-value ${selected ? "" : "is-placeholder"}`}>
          {selected?.label || placeholder}
        </span>
        <span className="ui-select-chevron" aria-hidden>
          <svg width="12" height="8" viewBox="0 0 12 8" fill="none">
            <path
              d="M1 1.5L6 6.5L11 1.5"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
      </button>
      {menu}
    </div>
  );
}
