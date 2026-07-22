import type { InputHTMLAttributes } from "react";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "defaultValue" | "onBlur" | "onInput" | "type" | "value"> & {
  type: "date" | "datetime-local" | "time";
  value: string;
  onCommit: (value: string) => void;
};

export function NativeScheduleInput({ type, value, onCommit, ...props }: Props) {
  return (
    <input
      {...props}
      key={`${type}:${value}`}
      type={type}
      defaultValue={value}
      onInput={(event) => {
        const nextValue = event.currentTarget.value;
        if (nextValue || type === "time") onCommit(nextValue);
      }}
      onBlur={(event) => {
        if (!event.currentTarget.value) onCommit("");
      }}
    />
  );
}
