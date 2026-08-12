"use client";

import { useRouter } from "next/navigation";

import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { Hero } from "@/components/sections/Hero";
import { HowItWorks } from "@/components/sections/HowItWorks";
import { ServiceCategories } from "@/components/sections/ServiceCategories";

export default function HomePage() {
  const router = useRouter();

  const start = (scope?: string) => {
    // A fresh conversation each time somebody comes in from the front page.
    // Carrying yesterday's problem into today's is confusing, and the results
    // beside it would be answering a question nobody just asked.
    localStorage.removeItem("sa_conversation");
    localStorage.removeItem("sa_services");
    router.push(scope ? `/chat?scope=${encodeURIComponent(scope)}` : "/chat");
  };

  return (
    <>
      <Navbar onStart={() => start()} />

      <main>
        <Hero
          onStart={() => start()}
          onProviderClick={() => router.push("/provider/register")}
        />
        <HowItWorks />
        <ServiceCategories onCategorySelect={(scope) => start(scope)} />
      </main>

      <Footer />
    </>
  );
}
