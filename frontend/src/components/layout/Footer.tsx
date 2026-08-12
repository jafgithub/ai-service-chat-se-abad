import { BRAND_NAME, BRAND_TAGLINE } from "@/constants";

const FOOTER_LINKS = {
  Company: [
    { label: "About Us", href: "#" },
    { label: "How It Works", href: "#how-it-works" },
    { label: "Services", href: "#services" },
  ],
  Support: [
    { label: "Contact Us", href: "#" },
    { label: "FAQs", href: "#" },
    { label: "Order Tracking", href: "#" },
  ],
  Legal: [
    { label: "Privacy Policy", href: "#" },
    { label: "Terms of Service", href: "#" },
  ],
};

export function Footer() {
  return (
    <footer id="footer" className="bg-gray-900 text-ink-faint">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-16 pb-8">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-10 mb-12">
          <div className="sm:col-span-2 lg:col-span-1">
            <div className="flex items-center gap-2 mb-4">
              <span className="w-9 h-9 rounded-control bg-gradient-to-br from-orange-500 to-rose-500 flex items-center justify-center text-white text-lg">
                📅
              </span>
              <span className="text-white font-extrabold text-xl">{BRAND_NAME}</span>
            </div>
            <p className="text-sm leading-relaxed mb-5">{BRAND_TAGLINE}</p>
            <div className="flex items-center gap-3">
              {["📧", "📞", "📍"].map((icon, i) => (
                <a
                  key={i}
                  href="#"
                  className="w-9 h-9 rounded-lg bg-gray-800 hover:bg-brand-500 hover:text-white flex items-center justify-center text-base transition-colors duration-200"
                >
                  {icon}
                </a>
              ))}
            </div>
          </div>

          {Object.entries(FOOTER_LINKS).map(([group, links]) => (
            <div key={group}>
              <h4 className="text-white font-semibold text-sm uppercase tracking-wider mb-4">
                {group}
              </h4>
              <ul className="space-y-2.5">
                {links.map((link) => (
                  <li key={link.label}>
                    <a
                      href={link.href}
                      className="text-sm hover:text-orange-400 transition-colors duration-200"
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="border-t border-gray-800 pt-8 mb-8">
          <div className="flex flex-col sm:flex-row gap-4 sm:gap-8 text-sm">
            <span className="flex items-center gap-2">
              <span className="text-orange-400">📧</span>
              orders@smartmarket.com
            </span>
            <span className="flex items-center gap-2">
              <span className="text-orange-400">📞</span>
              +1 (555) 000-0000
            </span>
            <span className="flex items-center gap-2">
              <span className="text-orange-400">📍</span>
              Market Square, City Center
            </span>
          </div>
        </div>

        <div className="border-t border-gray-800 pt-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-ink-muted">
          <p>© {new Date().getFullYear()} {BRAND_NAME}. All rights reserved.</p>
          <p>Powered by AI — built for speed.</p>
        </div>
      </div>
    </footer>
  );
}
