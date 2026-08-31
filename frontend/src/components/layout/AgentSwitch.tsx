"use client";

/**
 * Switching between the three agents, from inside any of them.
 *
 * A stopgap, and worth saying so: the intended way to move between agents is to
 * ask, and be taken there by the conversation. Until that exists, somebody who
 * opened the wrong door has to go back to smartzees.com and start again, which
 * is a worse experience than three buttons.
 *
 * The current agent is rendered as a button rather than a link, so the control
 * looks the same in all three places and the one you are already in does not
 * offer to reload the page you are on.
 */

const AGENTS = [
  { id: "market", label: "Market", icon: "\u{1F6D2}", href: "https://marketz.smartzees.com/chat" },
  { id: "service", label: "Service", icon: "\u{1F527}", href: "https://servicez.smartzees.com/chat" },
  { id: "community", label: "Community", icon: "\u{1F3D8}\u{FE0F}", href: "https://livz.smartzees.com/" },
];

export function AgentSwitch({ current }: { current: string }) {
  return (
    <nav
      aria-label="Switch assistant"
      className="flex items-center gap-0.5 rounded-full bg-black/15 p-0.5"
    >
      {AGENTS.map((a) => {
        const here = a.id === current;
        const shared =
          "flex items-center gap-1.5 rounded-full px-2.5 py-1.5 text-xs font-semibold transition-colors";
        return here ? (
          <span key={a.id} aria-current="page" className={`${shared} bg-white text-ink`}>
            <span aria-hidden>{a.icon}</span>
            <span className="hidden sm:inline">{a.label}</span>
          </span>
        ) : (
          <a
            key={a.id}
            href={a.href}
            title={`Go to Smart${a.label}`}
            className={`${shared} text-white/80 hover:bg-white/20 hover:text-white`}
          >
            <span aria-hidden>{a.icon}</span>
            <span className="hidden sm:inline">{a.label}</span>
          </a>
        );
      })}
    </nav>
  );
}
