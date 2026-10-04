"use client";

import { CheckIcon, ModelLogo, XIcon } from "../_components/icons";
import type { Ballot, RoundState } from "../_lib/debateClient";
import type { Seat } from "../_lib/panel";
import s from "./discussion.module.css";

const MAX_ROUNDS = 3;
const SHORT: Record<Ballot, string> = { Approve: "✓", Reject: "✕", Abstain: "–", "No Vote": "?" };
const PILL: Record<Ballot, string> = {
  Approve: s.pillApprove,
  Reject: s.pillReject,
  Abstain: s.pillAbstain,
  "No Vote": s.pillAbstain,
};

/**
 * Floating blue panel: the 3 panelists (their real logos and names), their live
 * votes for the current round, the tally, and the round controls.
 */
export function VotesPanel({
  seats,
  rounds,
  running,
  onNextRound,
  onChoose,
  className,
}: {
  seats: Seat[];
  rounds: RoundState[];
  running: boolean;
  onNextRound: () => void;
  onChoose: () => void;
  className?: string;
}) {
  const current = rounds.at(-1);
  const number = rounds.length;
  const votes = current ? current.answers.map((a) => a.vote) : [];
  const cast = votes.filter(Boolean) as Ballot[];
  const count = (b: Ballot) => cast.filter((v) => v === b).length;
  const canContinue = !!current && !running && current.status === "done" && number < MAX_ROUNDS;

  return (
    <aside className={`${s.float} ${s.floatRight} ${s.votes} ${className ?? ""}`} aria-label="Votes">
      <div className={s.floatHead}>
        <span>{current ? "Votes" : "Your panel"}</span>
        {current && (
          <span className={s.roundBadge}>
            Round {number} / {MAX_ROUNDS}
          </span>
        )}
      </div>

      {seats.length === 0 ? (
        <>
          <p className={s.votesEmpty}>Pick 3 models to seat your panel.</p>
          <button type="button" className={s.nextRound} onClick={onChoose}>
            Choose models
          </button>
        </>
      ) : (
        <ul className={s.voteList}>
          {seats.map((seat, i) => {
            const vote = votes[i];
            const answer = current?.answers[i];
            const history = rounds.slice(0, -1).map((r) => r.answers[i].vote ?? "No Vote");
            return (
              <li key={`${seat.provider}:${seat.model}:${i}`} className={s.voteItem}>
                <span className={s.voteLogo}>
                  <ModelLogo src={seat.logo} size={16} alt="" />
                </span>
                <span className={s.voteWho}>
                  <span className={s.voteId} title={seat.model}>
                    {seat.name}
                  </span>
                  <span className={s.votePlatform}>{seat.platform}</span>
                  {history.length > 0 && (
                    <span className={s.voteHistory} aria-label={`Earlier rounds: ${history.join(", ")}`}>
                      {history.map((v, r) => (
                        <span key={r}>
                          R{r + 1} {SHORT[v]}
                        </span>
                      ))}
                    </span>
                  )}
                </span>
                {vote ? (
                  <span className={`${s.votePill} ${PILL[vote]}`} title={answer?.error}>
                    {vote === "Approve" ? <CheckIcon size={10} strokeWidth={3} /> : vote === "Reject" ? <XIcon size={10} strokeWidth={3} /> : null}
                    {vote}
                  </span>
                ) : current?.status === "running" ? (
                  <span className={s.voteWaiting} aria-label="Thinking">
                    <span />
                    <span />
                    <span />
                  </span>
                ) : current ? (
                  <span className={`${s.votePill} ${s.pillAbstain}`}>No Vote</span>
                ) : (
                  <span className={s.voteReady}>Ready</span>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {current && (
        <>
          <div className={s.count}>
            <div className={s.countBar} role="img" aria-label={`${count("Approve")} approve, ${count("Reject")} reject, ${count("Abstain")} abstain`}>
              <span style={{ flexGrow: count("Approve"), background: "#FFFFFF" }} />
              <span style={{ flexGrow: count("Reject"), background: "rgba(255,255,255,0.35)" }} />
              <span style={{ flexGrow: count("Abstain") + count("No Vote"), background: "rgba(255,255,255,0.15)" }} />
              <span style={{ flexGrow: seats.length - cast.length, background: "transparent" }} />
            </div>
            <div className={s.countNumbers}>
              <span>
                <strong>{count("Approve")}</strong> approve
              </span>
              <span>
                <strong>{count("Reject")}</strong> reject
              </span>
              <span>
                <strong>{count("Abstain")}</strong> abstain
              </span>
            </div>
            <span className={s.countStatus}>
              {current.decision ? current.decision.headline : `Counting · ${cast.length} of ${seats.length} in`}
            </span>
          </div>

          <div className={s.rounds}>
            <span className={s.roundsLabel}>Rounds</span>
            <div className={s.roundSteps}>
              {Array.from({ length: MAX_ROUNDS }, (_, r) => (
                <span key={r} className={`${s.roundStep} ${r < number ? s.roundStepDone : ""} ${r === number - 1 ? s.roundStepCurrent : ""}`}>
                  {r < number - 1 || (r === number - 1 && current.status === "done") ? <CheckIcon size={10} strokeWidth={3} /> : null}
                  {r + 1}
                </span>
              ))}
            </div>
            {number < MAX_ROUNDS ? (
              <button type="button" className={s.nextRound} onClick={onNextRound} disabled={!canContinue}>
                {running ? `Round ${number} in progress…` : `Go for round ${number + 1}`}
              </button>
            ) : (
              <span className={s.roundsDone}>All {MAX_ROUNDS} rounds done</span>
            )}
          </div>
        </>
      )}

      {!current && seats.length > 0 && (
        <button type="button" className={s.changePanel} onClick={onChoose}>
          Change models
        </button>
      )}
    </aside>
  );
}
