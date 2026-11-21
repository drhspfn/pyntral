/** Accessible controlled choice primitives, shared by Pyntral and @pyntral/ui consumers. */
import {
  forwardRef, useEffect, useId, useImperativeHandle, useRef,
  type InputHTMLAttributes, type ReactNode,
} from "react";
import { Check, Minus } from "lucide-react";
import { changeGroupSelection } from "./controls-state";

export type ChoiceValue = string | number;
export interface ChoiceOption<T extends ChoiceValue> {
  value: T;
  label: ReactNode;
  description?: ReactNode;
  disabled?: boolean;
}
export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>,
  "type" | "checked" | "defaultChecked" | "onChange" | "children"> {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  indeterminate?: boolean;
  label?: ReactNode;
  description?: ReactNode;
}
/** Native checkbox semantics, including an indeterminate select-all state. */
export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox({
  checked, onCheckedChange, indeterminate = false, label, description, disabled,
  className = "", ...rest
}, forwardedRef) {
  const input = useRef<HTMLInputElement>(null);
  useImperativeHandle(forwardedRef, () => input.current!, []);
  useEffect(() => { if (input.current) input.current.indeterminate = indeterminate; }, [indeterminate]);
  return <label className={"ra-checkbox " + (label != null ? "ra-choice-labeled " : "") +
    (disabled ? "is-disabled " : "") + className}>
    <input {...rest} ref={input} type="checkbox" checked={checked} disabled={disabled}
      aria-checked={indeterminate ? "mixed" : checked}
      onChange={(event) => onCheckedChange(event.target.checked)} />
    <span className="ra-checkbox-mark" aria-hidden="true">
      {indeterminate ? <Minus size={12} strokeWidth={3}/> : <Check size={12} strokeWidth={3}/>}
    </span>
    {label != null && <span className="ra-choice-content"><span className="ra-choice-label">{label}</span>
      {description && <span className="ra-choice-description">{description}</span>}</span>}
  </label>;
});
export interface SwitchProps extends Omit<InputHTMLAttributes<HTMLInputElement>,
  "type" | "checked" | "defaultChecked" | "onChange" | "children"> {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label?: ReactNode;
  description?: ReactNode;
}
/** On/off control: keyboard-usable checkbox with switch semantics. */
export const Switch = forwardRef<HTMLInputElement, SwitchProps>(function Switch({
  checked, onCheckedChange, label, description, disabled, className = "", ...rest
}, ref) {
  return <label className={"ra-switch " + (disabled ? "is-disabled " : "") + className}>
    <input {...rest} ref={ref} type="checkbox" role="switch" checked={checked} disabled={disabled}
      onChange={(event) => onCheckedChange(event.target.checked)}/>
    <span className="ra-switch-track" aria-hidden="true"><span className="ra-switch-thumb"/></span>
    {label != null && <span className="ra-choice-content"><span className="ra-choice-label">{label}</span>
      {description && <span className="ra-choice-description">{description}</span>}</span>}
  </label>;
});
interface GroupBase<T extends ChoiceValue> {
  options: readonly ChoiceOption<T>[];
  label?: string;
  ariaLabel?: string;
  disabled?: boolean;
  className?: string;
  orientation?: "vertical" | "horizontal";
}
export interface CheckboxGroupProps<T extends ChoiceValue> extends GroupBase<T> {
  value: readonly T[];
  onValueChange: (values: T[]) => void;
  minSelected?: number;
  maxSelected?: number;
}
/** Multi-select group. Use RadioGroup for exclusive selection semantics. */
export function CheckboxGroup<T extends ChoiceValue>({
  options, value, onValueChange, label, ariaLabel, disabled = false,
  orientation = "vertical", className = "", minSelected = 0, maxSelected,
}: CheckboxGroupProps<T>) {
  const selected = new Set(value);
  return <fieldset className={"ra-choice-group ra-choice-" + orientation + " " + className}
    disabled={disabled} aria-label={ariaLabel || (label ? undefined : "Choose options")}>
    {label && <legend>{label}</legend>}
    {options.map((option) => {
      const checked = selected.has(option.value);
      const atMax = maxSelected !== undefined && value.length >= maxSelected;
      return <Checkbox key={String(option.value)} checked={checked} label={option.label}
        description={option.description}
        disabled={disabled || option.disabled || (!checked && atMax) || (checked && value.length <= minSelected)}
        onCheckedChange={(next) => onValueChange(changeGroupSelection(value, option.value, next,
          { minSelected, maxSelected }))}/>;
    })}
  </fieldset>;
}
export interface RadioGroupProps<T extends ChoiceValue> extends GroupBase<T> {
  value: T | null;
  onValueChange: (value: T) => void;
  name?: string;
}
/** Exactly one selected option; browser-native arrow-key navigation. */
export function RadioGroup<T extends ChoiceValue>({
  options, value, onValueChange, name, label, ariaLabel, disabled = false,
  orientation = "vertical", className = "",
}: RadioGroupProps<T>) {
  const generatedName = useId();
  return <fieldset className={"ra-choice-group ra-choice-" + orientation + " " + className}
    disabled={disabled} aria-label={ariaLabel || (label ? undefined : "Choose one option")}>
    {label && <legend>{label}</legend>}
    {options.map((option) => <label className={"ra-radio " + (option.disabled ? "is-disabled" : "")} key={String(option.value)}>
      <input type="radio" name={name ?? generatedName} value={String(option.value)}
        checked={value === option.value} disabled={disabled || option.disabled}
        onChange={() => onValueChange(option.value)}/>
      <span className="ra-radio-mark" aria-hidden="true"/>
      <span className="ra-choice-content"><span className="ra-choice-label">{option.label}</span>
        {option.description && <span className="ra-choice-description">{option.description}</span>}</span>
    </label>)}
  </fieldset>;
}
export interface ToggleGroupProps<T extends ChoiceValue> extends GroupBase<T> {
  value: T | readonly T[] | null;
  onValueChange: (value: T | T[] | null) => void;
  multiple?: boolean;
  maxSelected?: number;
  name?: string;
}
/** Segmented toggles. Single mode uses radios; multiple mode uses checkboxes. */
export function ToggleGroup<T extends ChoiceValue>({
  options, value, onValueChange, multiple = false, maxSelected,
  name, label, ariaLabel, disabled = false, className = "",
}: ToggleGroupProps<T>) {
  const generatedName = useId();
  const selected = Array.isArray(value) ? value as T[] : value == null ? [] : [value as T];
  return <fieldset className={"ra-toggle-group " + className} disabled={disabled}
    aria-label={ariaLabel || (label ? undefined : "Choose view")}>
    {label && <legend>{label}</legend>}
    <div className="ra-toggle-track">
      {options.map((option) => {
        const active = selected.includes(option.value);
        const atLimit = maxSelected !== undefined && selected.length >= maxSelected;
        return <label className={"ra-toggle-item " + (active ? "is-active" : "")} key={String(option.value)}>
          <input type={multiple ? "checkbox" : "radio"} name={name ?? generatedName}
            checked={active} disabled={disabled || option.disabled || (multiple && !active && atLimit)}
            value={String(option.value)} onChange={(event) => {
              if (!multiple) onValueChange(option.value);
              else onValueChange(changeGroupSelection(selected, option.value, event.target.checked,
                { maxSelected }));
            }}/>
          <span>{option.label}</span>
        </label>;
      })}
    </div>
  </fieldset>;
}
