import { IN_ORBIT, SEATED } from "../_lib/data";
import { HawkMark, ModelLogo } from "./icons";
import s from "./orbit.module.css";

const SEAT_TAG = {
  speaking: { label: "SPEAKING", className: s.tagSpeaking },
  approve: { label: "APPROVE", className: s.tagApprove },
  reject: { label: "REJECT", className: s.tagReject },
};

export function Orbit({ className }: { className?: string }) {
  return (
    <div
      className={`${s.orbit} ${className ?? ""}`}
      role="img"
      aria-label="Hawk at the center. GPT-OSS 120B is speaking, Qwen3 Coder approves, Llama 3.3 70B rejects. Eight more providers orbit outside."
    >
      <span aria-hidden="true" className={s.ringOuter} />
      <span aria-hidden="true" className={s.ringInner} />

      <div aria-hidden="true" className={s.orbitB}>
        {IN_ORBIT.map((body) => (
          <div key={body.name} className={`${s.body} ${s.bodySmall}`} style={{ left: body.left, top: body.top }}>
            <div className={s.upright}>
              <ModelLogo src={body.logo} size={20} />
            </div>
          </div>
        ))}
      </div>

      <div aria-hidden="true" className={s.orbitA}>
        {SEATED.map((seat) => (
          <span
            key={`beam-${seat.model}`}
            className={`${s.beam} ${seat.status === "speaking" ? s.beamSpeaking : ""}`}
            style={{ transform: `rotate(${seat.deg}deg)` }}
          />
        ))}
        {SEATED.map((seat) => {
          const tag = SEAT_TAG[seat.status];
          const speaking = seat.status === "speaking";
          return (
            <div key={seat.model} className={`${s.body} ${s.bodyLarge}`} style={{ left: seat.left, top: seat.top }}>
              <div className={s.upright}>
                {speaking && <span className={`${s.speakingRing} ${s.pulse}`} />}
                <div className={`${s.planet} ${speaking ? s.planetSpeaking : ""}`}>
                  <ModelLogo src={seat.logo} size={30} />
                </div>
                <div className={s.planetLabel}>
                  <span className={s.planetName}>{seat.model}</span>
                  <span className={`${s.tag} ${tag.className}`}>{tag.label}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div aria-hidden="true" className={s.sun}>
        <span className={`${s.sunGlow} ${s.pulse}`} />
        <div className={s.sunCore}>
          <HawkMark size={28} sun="#8FB0FF" ink="#FFFFFF" />
          Hawk
        </div>
      </div>
    </div>
  );
}
