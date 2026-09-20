"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth/AuthProvider";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await login(username, password);
      router.push("/");
    } catch {
      setError("Identifiants invalides");
    }
  }

  const field = "mb-2 w-full rounded-lg border border-line bg-s2 px-3 py-2 text-[13px] text-ink placeholder:text-ink3";
  return (
    <div className="grid h-dvh place-items-center bg-bg">
      <form onSubmit={submit} className="w-80 rounded-[12px] border border-line bg-s1 p-6">
        <h1 className="mb-4 text-[15px] font-bold">Argus — Connexion</h1>
        <input aria-label="Utilisateur" value={username} placeholder="Utilisateur"
               onChange={(e) => setUsername(e.target.value)} className={field} />
        <input aria-label="Mot de passe" type="password" value={password} placeholder="Mot de passe"
               onChange={(e) => setPassword(e.target.value)} className={field + " mb-3"} />
        {error ? <p className="mb-2 text-[12px] text-crit">{error}</p> : null}
        <button type="submit" className="w-full rounded-lg bg-brand px-3 py-2 text-[13px] font-bold text-white">
          Se connecter
        </button>
      </form>
    </div>
  );
}
