import { useEffect, useRef, type InputHTMLAttributes } from "react";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "defaultValue" | "onBlur" | "onInput" | "type" | "value"> & {
  type: "date" | "datetime-local" | "time";
  value: string;
  onCommit: (value: string) => void;
};

export function shouldCommitNativeScheduleValue(value: string): boolean {
  return Boolean(value);
}

export function NativeScheduleInput({ type, value, onCommit, ...props }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const previousValueRef = useRef(value);

  useEffect(() => {
    if (value === previousValueRef.current) return;
    previousValueRef.current = value;

    const input = inputRef.current;
    if (!input || input.ownerDocument.activeElement === input) return;
    input.value = value;
  }, [value]);

  return (
    <input
      {...props}
      ref={inputRef}
      type={type}
      defaultValue={value}
      onInput={(event) => {
        const nextValue = event.currentTarget.value;
        // Native date/time inputs can briefly report an empty value while a
        // segmented keyboard edit is still in progress. Commit clearing on
        // blur instead of resetting the parent state during that edit.
        if (shouldCommitNativeScheduleValue(nextValue)) onCommit(nextValue);
      }}
      onBlur={(event) => {
        const nextValue = event.currentTarget.value;
        if (!nextValue || nextValue !== value) onCommit(nextValue);
      }}
    />
  );
}
