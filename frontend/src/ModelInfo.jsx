import { useId, useRef } from "react";

function versionDate(version) {
  const match = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})/.exec(
    version || "",
  );
  if (!match) return "Unavailable";
  const [, year, month, day, hour, minute, second] = match;
  return new Intl.DateTimeFormat("en-SG", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(
    new Date(Date.UTC(+year, +month - 1, +day, +hour, +minute, +second)),
  );
}

export default function ModelInfo({ version, model = "Discovery models" }) {
  const dialog = useRef(null);
  const titleId = useId();
  return (
    <>
      <button
        className="why model-info-button"
        type="button"
        aria-haspopup="dialog"
        onClick={() => dialog.current?.showModal()}
      >
        About this model
      </button>
      <dialog
        ref={dialog}
        className="model-dialog"
        aria-labelledby={titleId}
      >
        <p className="eyebrow">MODEL CARD</p>
        <h2 id={titleId}>About this model</h2>
        <p>
          <strong>{model}</strong>
        </p>
        <dl>
          <dt>Version</dt>
          <dd>{version || "Unavailable"}</dd>
          <dt>Version date (UTC)</dt>
          <dd>{versionDate(version)}</dd>
        </dl>
        <p className="notice">
          <strong>SIMULATED DATA</strong>
          <br />
          Users, orders, events, prices and stock are simulated. Product names
          and photographs refer to real fragrances; this catalogue does not
          confirm supplier authenticity or availability.
        </p>
        <p>
          Recommendations show ranking signals, not a probability that you will
          like a scent. Forecast bands describe evaluation outputs, not
          guaranteed future demand. Results demonstrate methods and pipeline
          behaviour, not real customer or commercial performance.
        </p>
        <a href="/intelligence">View the evaluation and method notes</a>
        <form method="dialog">
          <button className="button">Close model information</button>
        </form>
      </dialog>
    </>
  );
}
