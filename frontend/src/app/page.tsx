import Link from "next/link";
import { CopyButton } from "./_components/CopyButton";
import { Orbit } from "./_components/Orbit";
import { RecordTabs } from "./_components/RecordTabs";
import { SiteFooter } from "./_components/SiteFooter";
import {
  ArrowRightIcon,
  CheckIcon,
  ModelLogo,
  PlayIcon,
  HawkMark,
} from "./_components/icons";
import {
  ACTIVITY,
  FEED,
  LOGOS,
  PANEL,
  PROVIDER_KIND_LABEL,
  PROVIDER_ROWS,
  QUESTION,
  SPEAKING_LANES,
  STARS,
  STATS,
  type ProviderKind,
} from "./_lib/data";
import s from "./landing.module.css";

const INSTALL_COMMANDS = `python -m pip install .\nhawk\n/hawk 2 ${QUESTION}`;

const KIND_CLASS: Record<ProviderKind, string> = {
  free: s.kindFree,
  local: s.kindLocal,
  cli: s.kindCli,
};

export default function LandingPage() {
  return (
    <div className={s.page}>
      <Hero />
      <main>
        <HowItWorks />
        <OnTheRecord />
        <Providers />
        <GetStarted />
      </main>
      <SiteFooter />
    </div>
  );
}

/* ------------------------------------------------------------------ hero */

function Hero() {
  return (
    <div className={s.sky}>
      {STARS.map((star, i) => (
        <span
          key={i}
          aria-hidden="true"
          className={s.star}
          style={{ left: star.left, top: star.top, width: star.size, height: star.size, opacity: star.opacity }}
        />
      ))}
      <svg aria-hidden="true" viewBox="0 0 1200 220" preserveAspectRatio="none" className={s.mountains}>
        <path d="M0 220V150l90-48 70 30 110-86 90 64 60-22 120 90 80-56 110 70 90-104 100 80 70-26 90 54 120-60V220z" fill="#3A2F5E" opacity="0.55" />
        <path d="M0 220v-44l120-34 100 26 140-58 130 62 110-30 150 50 120-40 140 34 90-20V220z" fill="#1C1736" />
      </svg>

      <header className={`${s.container} ${s.nav}`}>
        <Link href="/" className={s.brand}>
          <HawkMark sun="#8FB0FF" ink="#FFFFFF" />
          Hawk
        </Link>
        <nav aria-label="Main" className={s.navLinks}>
          <a href="#demo" className={s.navLink}>Live demo</a>
          <a href="#how" className={s.navLink}>How it works</a>
          <a href="#providers" className={s.navLink}>Providers</a>
          <Link href="/discussion" className={s.navLink}>Discussions</Link>
          <Link href="/discussion" className={s.btnLight}>Start a discussion</Link>
        </nav>
      </header>

      <section className={`${s.container} ${s.hero}`}>
        <span className={s.badge}>
          <span className={`${s.dot} ${s.blink}`} style={{ background: "var(--accent-light)" }} />
          A panel is in session
        </span>
        <h1 className={s.heroTitle}>
          Don&apos;t trust one model.
          <br />
          Let <em>Hawk</em> convene a panel.
        </h1>
        <p className={s.heroText}>
          Several AI models circle your question. They discuss, argue, improve each other&apos;s answers, vote Approve or
          Reject — and one of them writes the conclusion.
        </p>
        <div className={s.ctaRow}>
          <Link href="/discussion" className={s.btnPrimary}>
            Start a discussion
            <ArrowRightIcon />
          </Link>
          <a href="#demo" className={s.btnGhost}>
            <PlayIcon />
            Watch it debate
          </a>
        </div>
      </section>

      <section id="demo" aria-label="Live demo" className={s.demo}>
        <DemoWindow />
      </section>
    </div>
  );
}

function DemoWindow() {
  return (
    <div className={s.window}>
      <div className={s.chrome}>
        <span aria-hidden="true" className={s.lights}>
          <span />
          <span />
          <span />
        </span>
        <span className={s.title}>
          <span className={s.titleIcon} aria-hidden="true">
            <HawkMark size={13} sun="#FFFFFF" ink="#FFFFFF" />
          </span>
          Hawk — live debate
        </span>
        <span className={s.chromeRight}>ROUND 2/3</span>
      </div>

      <div aria-hidden="true" className={s.activity}>
        {ACTIVITY.map((bar, i) => (
          <span
            key={i}
            className={`${s.bar} ${bar.recent ? s.barRecent : ""}`}
            style={{ height: bar.height, animationDelay: bar.delay }}
          />
        ))}
      </div>

      <div className={s.panes}>
        <div className={s.transcriptPane}>
          <div className={s.paneHead}>
            <span>TRANSCRIPT</span>
            <span className={s.live}>
              <span className={`${s.dot} ${s.blink}`} style={{ background: "var(--accent)" }} />
              LIVE
            </span>
          </div>
          {FEED.map((item) => (
            <div key={item.time} className={s.feedItem} style={{ borderLeftColor: item.color, opacity: item.opacity }}>
              <div className={s.feedTop}>
                <span className={s.feedTime}>{item.time}</span>
                <span className={s.feedEvent}>{item.event}</span>
                {item.tag ? (
                  <span className={`${s.tag} ${item.tag === "APPROVE" ? s.tagApprove : s.tagReject}`}>{item.tag}</span>
                ) : (
                  <span className={s.feedMeta}>{item.meta}</span>
                )}
              </div>
              <span className={s.feedText}>{item.text}</span>
            </div>
          ))}
        </div>

        <div className={s.orbitPane}>
          <div className={s.paneHead}>
            <span>PANEL</span>
            <span className={s.counts}>
              3 SEATED <span style={{ color: "var(--caption)" }}>·</span>
              <span style={{ color: "var(--accent)" }}>1 SPEAKING</span>
              <span style={{ color: "var(--caption)" }}>·</span> 8 IN ORBIT
            </span>
          </div>
          <div className={s.orbitStage}>
            <Orbit />
          </div>
          <div className={s.legend}>
            <span>
              <span className={s.legendDot} style={{ background: "var(--accent)" }} />
              SPEAKING
            </span>
            <span>
              <span className={s.legendDot} style={{ border: "1px solid #9AA1B0" }} />
              SEATED
            </span>
            <span>
              <span className={s.legendDot} style={{ border: "1px dashed #9AA1B0" }} />
              IN ORBIT
            </span>
          </div>
        </div>
      </div>

      <div className={s.statusBar}>
        <span className={s.statusLabel}>
          <span className={`${s.dot} ${s.blink}`} style={{ background: "var(--accent-light)" }} />
          CHALLENGE
        </span>
        <span className={s.statusText}>
          gpt-oss-120b → llama-3.3-70b “short-lived tokens still leave a window after logout”
        </span>
        <span className={s.statusTime}>2.1k tok · 14:23:06</span>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------- how it works */

function HowItWorks() {
  return (
    <section id="how" className={`${s.container} ${s.how}`}>
      <h2 className={s.h2}>How Hawk reaches a decision</h2>

      <div className={s.cards}>
        <article className={`${s.card} ${s.cardBlue}`}>
          <div className={s.cardIntro}>
            <h3 className={s.cardTitle}>
              The panel <span className={s.pill}>debates</span>
            </h3>
            <p className={s.cardText}>
              Each model answers, reads the others, and pushes back. Every round sharpens the argument instead of
              averaging it.
            </p>
          </div>
          <div className={s.lanes} role="img" aria-label="Turn order: each panelist speaks three times across the debate.">
            {PANEL.map((p, i) => (
              <div key={p.id} className={s.lane}>
                <span className={s.laneLogo}>
                  <ModelLogo src={p.logo} size={16} />
                </span>
                <div className={s.laneTrack}>
                  {SPEAKING_LANES[i].map((on, j) => (
                    <span key={j} className={on ? s.laneOn : undefined} />
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className={s.quote}>
            <span>Llama 3.3 70B challenges Qwen3 Coder</span>
            <span>“Refresh tokens add a second failure path. What happens when the refresh call races a logout?”</span>
          </div>
        </article>

        <article className={`${s.card} ${s.cardGray}`}>
          <div className={s.cardIntro}>
            <h3 className={s.cardTitle}>
              Every panelist <span className={s.pill}>votes</span>
            </h3>
            <p className={s.cardText}>
              Approve, Reject or Abstain — each with a one-line reason, so you can see exactly where consensus breaks.
            </p>
          </div>
          <div className={s.voteBox}>
            <span className={s.voteBoxCaption}>Proposal: keep server-side sessions</span>
            {PANEL.map((p) => (
              <div key={p.id} className={s.voteRow}>
                <span className={s.voteLogo}>
                  <ModelLogo src={p.logo} size={18} />
                </span>
                <div className={s.voteWho}>
                  <strong>{p.name}</strong>
                  <span>{p.reason}</span>
                </div>
                <span className={`${s.voteChip} ${p.vote === "Approve" ? s.voteChipApprove : s.voteChipReject}`}>
                  {p.vote}
                </span>
              </div>
            ))}
            <div className={s.tally} aria-hidden="true">
              <span style={{ flex: "2 1 0", background: "#5FD4BE" }} />
              <span style={{ flex: "1 1 0", background: "#FF9A62" }} />
            </div>
            <div className={s.tallyLegend}>
              <span>2 Approve</span>
              <span>1 Reject</span>
              <span>0 Abstain</span>
            </div>
          </div>
        </article>
      </div>

      <Verdict />
    </section>
  );
}

function Verdict() {
  return (
    <article className={s.verdict}>
      <span aria-hidden="true" className={`${s.glow} ${s.glowA}`} />
      <span aria-hidden="true" className={`${s.glow} ${s.glowB}`} />
      <span aria-hidden="true" className={s.ringDeco} />
      <span aria-hidden="true" className={s.sphere} />
      <span aria-hidden="true" className={s.dotGrid} />

      <div className={s.verdictIntro}>
        <span className={s.glassBadge}>
          <span className={s.dot} style={{ background: "#FFFFFF" }} />
          DEBATE COMPLETE
        </span>
        <h3 className={s.verdictTitle}>
          One of them writes the <em>verdict.</em>
        </h3>
        <p className={s.verdictLead}>
          When the last vote is in, a synthesizer reads every round and every reason — and hands you one clear
          decision.
        </p>
      </div>

      <div className={s.glass}>
        <div className={s.glassChrome}>
          <span aria-hidden="true" className={s.lights}>
            <span />
            <span />
            <span />
          </span>
          <span className={s.glassUrl}>localhost:3000/hawk/verdict</span>
          <span className={s.approvedTag}>
            <CheckIcon size={11} strokeWidth={3} />
            APPROVED 2–1
          </span>
        </div>

        <div className={s.glassBody}>
          <div className={s.glassVotes}>
            <div className={s.glassHead}>VOTES</div>
            {PANEL.map((p) => (
              <div key={p.id} className={s.glassVote}>
                <span className={s.glassLogo}>
                  <ModelLogo src={p.logo} size={16} />
                </span>
                <span className={s.glassId}>{p.id}</span>
                <span className={`${s.glassTag} ${p.vote === "Approve" ? s.glassTagApprove : s.glassTagReject}`}>
                  {p.vote.toUpperCase()}
                </span>
              </div>
            ))}
            <div className={s.glassTally} aria-label="2 approve, 1 reject" role="img">
              <span style={{ flex: "2 1 0", background: "#FFFFFF" }} />
              <span style={{ flex: "1 1 0", background: "rgba(255,255,255,0.22)" }} />
            </div>
          </div>

          <div className={s.glassVerdict}>
            <div className={s.glassHead} style={{ paddingInline: 20 }}>
              <span>VERDICT</span>
              <span className={s.glassAuthor}>
                <span className={s.glassAuthorLogo}>
                  <ModelLogo src={LOGOS.openai} size={11} />
                </span>
                GPT-OSS-120B
              </span>
            </div>
            <div className={s.glassDecision}>
              <span className={s.decision}>
                Keep sessions. <em>Harden them.</em>
                <span aria-hidden="true" className={`${s.decisionCaret} ${s.caret}`} />
              </span>
              <span className={s.decisionText}>
                Switching auth.py to JWT means building token revocation for no clear gain. The one dissent is real,
                but not urgent.
              </span>
            </div>
            <dl className={s.glassNotes}>
              <div className={s.glassNote}>
                <dt>AGREED</dt>
                <dd>Sessions already work with the existing middleware.</dd>
              </div>
              <div className={s.glassNote}>
                <dt style={{ color: "#C9D6FF" }}>STILL OPEN</dt>
                <dd>A future mobile client may need stateless tokens.</dd>
              </div>
              <div className={s.glassNote}>
                <dt>DO NEXT</dt>
                <dd>Secure, HttpOnly, SameSite cookies; rotate the session ID on login.</dd>
              </div>
            </dl>
          </div>
        </div>

        <div className={s.glassStatus}>
          <span className={s.live} style={{ color: "#FFFFFF" }}>
            <span className={`${s.dot} ${s.blink}`} style={{ background: "#FFFFFF" }} />
            VERDICT
          </span>
          <span className={s.statusText} style={{ flexBasis: 220 }}>
            synthesized by gpt-oss-120b · 3 rounds · 9 turns · 3 votes
          </span>
          <span style={{ color: "#C9D6FF" }}>14:24:10</span>
        </div>
      </div>
    </article>
  );
}

/* --------------------------------------------------------- on the record */

function OnTheRecord() {
  return (
    <section id="record" className={`${s.container} ${s.record}`}>
      <div className={s.recordStage}>
        <div className={s.paper}>
          <div className={s.paperMeta}>
            Saturday, Oct 3 ·
            <span className={s.avatars}>
              {PANEL.map((p) => (
                <span key={p.id}>
                  <ModelLogo src={p.logo} size={12} />
                </span>
              ))}
            </span>
            <span style={{ marginLeft: 6 }}>Qwen3 Coder, Llama 3.3, +1 more</span>
          </div>
          <div className={s.paperTitle}>Refactor auth.py: JWT or server-side sessions?</div>
          <RecordTabs />
        </div>
      </div>

      <div className={s.stats}>
        <h2 className={s.h2}>Every argument, on the record</h2>
        {STATS.map((stat) => (
          <div key={stat.title} className={s.stat}>
            <div className={s.statBig}>{stat.big}</div>
            <div className={s.statBody}>
              <span className={s.statTitle}>{stat.title}</span>
              <span className={s.statText}>{stat.text}</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------- providers */

function Providers() {
  return (
    <section id="providers" aria-labelledby="providers-title" className={s.providers}>
      <div className={`${s.container} ${s.providersHead}`}>
        <div>
          <span className={s.eyebrow}>Providers</span>
          <h2 id="providers-title" className={s.h2}>Seat any model at the table</h2>
        </div>
        <p>
          Mix free APIs, models running on your own machine, and the coding CLIs you already subscribe to — all on the
          same panel.
        </p>
      </div>

      <div className={s.marquee}>
        {PROVIDER_ROWS.map((row, r) => (
          <div key={r} className={s.marqueeRow}>
            {/* The row is rendered twice so the -50% slide loops seamlessly. */}
            <div className={`${s.track} ${r === 1 ? s.trackReverse : ""}`}>
              {[...row, ...row].map((provider, i) => (
                <div key={i} className={s.providerCard} aria-hidden={i >= row.length ? true : undefined}>
                  <span className={s.providerLogo}>
                    <ModelLogo src={provider.logo} size={28} />
                  </span>
                  <div>
                    <span className={s.providerName}>{provider.name}</span>
                    <span className={`${s.providerKind} ${KIND_CLASS[provider.kind]}`}>
                      {PROVIDER_KIND_LABEL[provider.kind]}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className={`${s.container} ${s.providerSummary}`}>
        <span>
          <span className={s.summaryDot} style={{ background: "var(--accent)" }} />
          <strong>7</strong> free APIs
        </span>
        <span>
          <span className={s.summaryDot} style={{ background: "var(--reject)" }} />
          <strong>2</strong> paid APIs
        </span>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------- get started */

function GetStarted() {
  return (
    <section id="start" className={`${s.container} ${s.start}`}>
      <div className={s.startCard}>
        <div className={s.startIntro}>
          <h2 className={s.h2}>Convene your first panel</h2>
          <p>Install it, paste a free key in the setup wizard, and ask your first question. No paid subscription required.</p>
          <Link href="/discussion" className={s.btnPrimary}>Start a discussion</Link>
        </div>

        <div className={s.terminal}>
          <div className={s.terminalBar}>
            <span aria-hidden="true" className={s.macLights}>
              <span style={{ background: "#FF5F57" }} />
              <span style={{ background: "#FEBC2E" }} />
              <span style={{ background: "#28C840" }} />
            </span>
            <span className={s.terminalTitle}>
              <svg width="16" height="13" viewBox="0 0 16 13" aria-hidden="true">
                <path d="M0 2a2 2 0 0 1 2-2h4l1.5 1.6H14a2 2 0 0 1 2 2V11a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2z" fill="#6FB3F2" />
                <path d="M0 4h16v7a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2z" fill="#8CC6F7" />
              </svg>
              hawk — -zsh — 80×24
            </span>
            <CopyButton text={INSTALL_COMMANDS} label="Copy commands" className={s.copy} />
          </div>
          <pre className={s.terminalBody}>
            {"you@MacBook-Air ~ % python -m pip install .\n"}
            <span className={s.termDim}>Successfully installed hawk-0.1.0</span>
            {"\nyou@MacBook-Air ~ % hawk\n"}
            <span className={s.termYou}>You:</span>
            {` /hawk 2 ${QUESTION}\n`}
            <span className={s.termDim}>Convening 3 panelists…</span>{" "}
            <span aria-hidden="true" className={`${s.termCursor} ${s.caret}`} />
          </pre>
        </div>
      </div>
    </section>
  );
}
