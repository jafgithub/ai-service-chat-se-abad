"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { Hero } from "@/components/sections/Hero";
import { HowItWorks } from "@/components/sections/HowItWorks";
import { ProductCategories } from "@/components/sections/ProductCategories";
import { PartnerModal } from "@/components/ui/PartnerModal";

export default function HomePage() {
  const router = useRouter();
  const [partnerModalOpen, setPartnerModalOpen] = useState(false);

  const startOrdering = (scope?: string) => {
    localStorage.removeItem("chat_messages");
    localStorage.removeItem("chat_products");
    const url = scope ? `/chat?scope=${encodeURIComponent(scope)}` : "/chat";
    router.push(url);
  };

  return (
    <>
      <Navbar
        onStartOrdering={() => startOrdering()}
        onPartnerClick={() => setPartnerModalOpen(true)}
      />

      <main>
        <Hero
          onStartOrdering={() => startOrdering()}
          onPartnerClick={() => setPartnerModalOpen(true)}
        />
        <HowItWorks />
        <ProductCategories onCategorySelect={(scope) => startOrdering(scope)} />
      </main>

      <Footer />

      <PartnerModal
        open={partnerModalOpen}
        onClose={() => setPartnerModalOpen(false)}
      />
    </>
  );
}
