"use client";

import {useEffect, useRef} from "react";

export function CommissionField({label, help}: {label: string; help: string}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const automaticValue = useRef("");

  useEffect(() => {
    const commission = inputRef.current;
    const form = commission?.form;
    if (!commission || !form) return;

    const calculate = () => {
      if (commission.value && commission.value !== automaticValue.current) return;
      const value = (name: string) => {
        const field = form.elements.namedItem(name);
        return field instanceof HTMLInputElement || field instanceof HTMLSelectElement
          ? field.value.replace(",", ".") : "";
      };
      const quantity = Number(value("quantity"));
      const price = Number(value("price_per_share"));
      const total = Number(value("total_amount"));
      const side = value("type");
      if (![quantity, price, total].every(Number.isFinite) || quantity <= 0 || price <= 0) {
        if (commission.value === automaticValue.current) commission.value = "";
        automaticValue.current = "";
        return;
      }
      const gross = quantity * price;
      const inferred = side === "sell" ? gross - total : total - gross;
      if (inferred < 0) return;
      automaticValue.current = inferred.toFixed(2);
      commission.value = automaticValue.current;
    };

    form.addEventListener("input", calculate);
    form.addEventListener("change", calculate);
    return () => {
      form.removeEventListener("input", calculate);
      form.removeEventListener("change", calculate);
    };
  }, []);

  return <label>{label}
    <input ref={inputRef} name="commission" inputMode="decimal"
      pattern="[0-9]+([.,][0-9]{1,2})?" aria-describedby="commission-help"/>
    <small id="commission-help">{help}</small>
  </label>;
}
