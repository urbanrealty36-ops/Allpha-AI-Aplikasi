import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Linking, Pressable, Text, View } from "react-native";

const apiBase = (process.env.EXPO_PUBLIC_API_BASE_URL || "https://api.allpha.web.id").replace(/\/$/, "");
type Product = { product_key: string; name: string; description?: string | null; purpose: string; amount_minor: number; currency: string; billing_interval?: string | null; credits_grant: number; monthly_credits_grant: number };
type Order = { id: string; product_name: string; amount_minor: number; currency: string; status: string; created_at: string };
type Subscription = { plan_key: string; status: string; current_period_end?: string | null } | null;

function money(amountMinor: number, currency: string) {
  const format = new Intl.NumberFormat("id-ID", { style: "currency", currency: currency.toUpperCase() });
  return format.format(amountMinor / (10 ** (format.resolvedOptions().maximumFractionDigits ?? 2)));
}
function key() { return "native-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 14); }

function ActionButton({ title, onPress, disabled }: { title: string; onPress: () => void; disabled?: boolean }) {
  return <Pressable accessibilityRole="button" onPress={onPress} disabled={disabled} style={{ borderRadius: 12, padding: 13, backgroundColor: "#A5B4FC", opacity: disabled ? 0.45 : 1, alignItems: "center" }}><Text style={{ color: "#11162B", fontWeight: "800" }}>{title}</Text></Pressable>;
}

export function BillingCenter({ getAccessToken }: { getAccessToken: () => Promise<string> }) {
  const [products, setProducts] = useState<Product[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [subscription, setSubscription] = useState<Subscription>(null);
  const [balance, setBalance] = useState<number | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const request = useCallback(async (path: string, init: RequestInit = {}) => {
    const token = await getAccessToken();
    const response = await fetch(apiBase + path, { ...init, headers: {
      Accept: "application/json", ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...(init.headers || {}), Authorization: "Bearer " + token,
    }, cache: "no-store" });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload?.detail?.message || payload?.error?.message || "Billing API gagal (" + response.status + ").");
    return payload;
  }, [getAccessToken]);

  const load = useCallback(async () => {
    const [catalog, history, plan, credits] = await Promise.all([
      request("/v1/billing/catalog"),
      request("/v1/billing/orders?limit=10"),
      request("/v1/billing/subscription"),
      request("/v1/credits/balance").catch(() => null),
    ]);
    setProducts(catalog.items || []); setEnabled(catalog.checkout_enabled === true);
    setOrders(history.items || []); setSubscription(plan.subscription || null);
    setBalance(typeof credits?.available_credits === "number" ? credits.available_credits : null);
  }, [request]);

  useEffect(() => {
    let active = true;
    void load().catch(cause => { if (active) setError(cause instanceof Error ? cause.message : "Billing tidak dapat dimuat."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [load]);

  async function checkout(product: Product) {
    setBusy(product.product_key); setError(""); setNotice("");
    try {
      const result = await request("/v1/billing/checkout", {
        method: "POST", headers: { "Idempotency-Key": key() },
        body: JSON.stringify({ product_key: product.product_key }),
      });
      if (!result.checkout_url) throw new Error("URL Stripe Checkout tidak tersedia.");
      await Linking.openURL(result.checkout_url);
      setNotice("Stripe Checkout dibuka. Status transaksi akan diperbarui setelah webhook terverifikasi.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Checkout gagal dibuat."); }
    finally { setBusy(null); }
  }
  async function manageSubscription() {
    setError(""); setNotice("");
    try {
      const result = await request("/v1/billing/portal", { method: "POST", body: "{}" });
      if (!result.url) throw new Error("Stripe Customer Portal tidak tersedia.");
      await Linking.openURL(result.url);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Portal subscription gagal dibuka."); }
  }


  return <View style={{ gap: 14 }}>
    <Text style={{ color: "#A5B4FC", fontSize: 11, fontWeight: "800", letterSpacing: 2 }}>ACCOUNT · ECONOMY</Text>
    <Text style={{ color: "#F7F8FF", fontSize: 23, fontWeight: "800" }}>Billing & AI Credits</Text>
    <Text style={{ color: "#A5ADC3", fontSize: 13 }}>Stripe adalah payment provider Allpha. Redirect bukan bukti pembayaran; entitlement hanya berubah setelah webhook diverifikasi.</Text>
    <View style={{ backgroundColor: "#141B31", borderWidth: 1, borderColor: "#29314B", borderRadius: 18, padding: 15, gap: 8 }}>
      <Text style={{ color: "#A5ADC3", fontSize: 12 }}>AI Credits tersedia</Text>
      <Text style={{ color: "#F7F8FF", fontSize: 26, fontWeight: "800" }}>{balance === null ? "—" : balance.toLocaleString("id-ID")}</Text>
      <Text style={{ color: "#A5ADC3", fontSize: 12 }}>Subscription: {subscription ? subscription.plan_key + " · " + subscription.status : "Free"}</Text>
      {subscription ? <ActionButton title="Kelola subscription di Stripe" disabled={busy !== null} onPress={() => void manageSubscription()}/> : null}
      <Text style={{ color: enabled ? "#86EFAC" : "#FBBF24", fontSize: 12 }}>{enabled ? "Checkout Stripe aktif untuk produk yang dipublikasikan." : "Checkout belum diaktifkan; menunggu konfigurasi dan persetujuan billing."}</Text>
    </View>
    {error ? <Text accessibilityRole="alert" style={{ color: "#FCA5A5", fontSize: 13 }}>{error}</Text> : null}
    {notice ? <Text accessibilityLiveRegion="polite" style={{ color: "#86EFAC", fontSize: 13 }}>{notice}</Text> : null}
    <Text style={{ color: "#F7F8FF", fontSize: 18, fontWeight: "700" }}>Paket & top-up</Text>
    {loading ? <ActivityIndicator color="#A5B4FC"/> : products.length ? products.map(product => <View key={product.product_key} style={{ backgroundColor: "#141B31", borderWidth: 1, borderColor: "#29314B", borderRadius: 18, padding: 15, gap: 8 }}>
      <Text style={{ color: "#A5B4FC", fontSize: 10, fontWeight: "800", letterSpacing: 1 }}>{product.purpose === "premium_subscription" ? "SUBSCRIPTION" : "AI CREDITS TOP-UP"}</Text>
      <Text style={{ color: "#F7F8FF", fontSize: 17, fontWeight: "700" }}>{product.name}</Text>
      <Text style={{ color: "#A5ADC3", fontSize: 13 }}>{product.description || ""}</Text>
      <Text style={{ color: "#F7F8FF", fontSize: 22, fontWeight: "800" }}>{money(product.amount_minor, product.currency)}</Text>
      <Text style={{ color: "#A5ADC3", fontSize: 12 }}>{product.purpose === "ai_credit_topup" ? product.credits_grant.toLocaleString("id-ID") + " AI Credits" : product.monthly_credits_grant.toLocaleString("id-ID") + " AI Credits per paid invoice · " + (product.billing_interval || "periode paket")}</Text>
      <ActionButton title={busy === product.product_key ? "Menyiapkan checkout…" : enabled ? "Lanjutkan ke Stripe" : "Checkout belum tersedia"} disabled={!enabled || busy !== null} onPress={() => void checkout(product)}/>
    </View>) : <Text style={{ color: "#A5ADC3", fontSize: 13 }}>Belum ada paket aktif. Harga dan jumlah kredit tidak dibuat otomatis.</Text>}
    <Text style={{ color: "#F7F8FF", fontSize: 18, fontWeight: "700" }}>Riwayat pesanan</Text>
    {orders.length ? orders.map(order => <View key={order.id} style={{ paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: "#29314B", gap: 4 }}>
      <Text style={{ color: "#F7F8FF", fontWeight: "600" }}>{order.product_name}</Text>
      <Text style={{ color: "#A5ADC3", fontSize: 12 }}>{money(order.amount_minor, order.currency)} · {order.status}</Text>
      <Text style={{ color: "#747E9A", fontSize: 10 }}>{order.id}</Text>
    </View>) : <Text style={{ color: "#A5ADC3", fontSize: 13 }}>Belum ada transaksi.</Text>}
  </View>;
}
