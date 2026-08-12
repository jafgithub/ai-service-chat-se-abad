"use client";

import { useState } from "react";
import { partnersApi } from "@/lib/api/endpoints";

interface PartnerModalProps {
  open: boolean;
  onClose: () => void;
}

export function PartnerModal({ open, onClose }: PartnerModalProps) {
  const [form, setForm] = useState({ name: "", email: "", phone: "", address: "" });
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await partnersApi.submit({
        name: form.name,
        email: form.email,
        phone: form.phone || undefined,
        address: form.address || undefined,
      });
      setSuccess(true);
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setForm({ name: "", email: "", phone: "", address: "" });
    setSuccess(false);
    setError("");
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={handleClose} />
      <div className="relative w-full max-w-md bg-surface rounded-card shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-br from-orange-500 to-rose-500 px-6 py-5">
          <button
            onClick={handleClose}
            className="absolute top-4 right-4 w-8 h-8 rounded-full bg-surface/20 hover:bg-surface/30 flex items-center justify-center text-white transition-colors"
            aria-label="Close"
          >
            ✕
          </button>
          <h2 className="text-xl font-extrabold text-white">Become a Partner</h2>
          <p className="text-orange-100 text-sm mt-1">Join our growing network of local markets</p>
        </div>

        <div className="px-6 py-6">
          {success ? (
            <div className="text-center py-6">
              <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center text-3xl mx-auto mb-4">
                ✅
              </div>
              <h3 className="text-lg font-bold text-ink mb-2">Thank you!</h3>
              <p className="text-ink-muted text-sm">We received your inquiry and will be in touch shortly.</p>
              <button
                onClick={handleClose}
                className="mt-6 px-6 py-2 bg-brand-500 hover:bg-brand-600 text-white font-semibold rounded-control text-sm transition-colors"
              >
                Close
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div>
                <label className="block text-sm font-semibold text-ink-muted mb-1">Full Name *</label>
                <input
                  type="text"
                  required
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="John Smith"
                  className="w-full border border-line rounded-control px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-ink-muted mb-1">Email Address *</label>
                <input
                  type="email"
                  required
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  placeholder="john@example.com"
                  className="w-full border border-line rounded-control px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-ink-muted mb-1">Phone Number</label>
                <input
                  type="tel"
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  placeholder="+1 (555) 000-0000"
                  className="w-full border border-line rounded-control px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-ink-muted mb-1">Business Address</label>
                <input
                  type="text"
                  value={form.address}
                  onChange={(e) => setForm({ ...form, address: e.target.value })}
                  placeholder="123 Market St, City, State"
                  className="w-full border border-line rounded-control px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400 focus:border-transparent"
                />
              </div>

              {error && (
                <p className="text-red-500 text-sm text-center">{error}</p>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-brand-500 hover:bg-brand-600 disabled:opacity-60 text-white font-bold py-3 rounded-control text-sm transition-colors mt-1"
              >
                {loading ? "Submitting..." : "Submit Inquiry"}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
