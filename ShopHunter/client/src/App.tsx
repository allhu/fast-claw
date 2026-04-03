import React, { useEffect, useState } from "react";

type Product = {
  id: number;
  name: string;
  description: string | null;
  price: number;
  createdAt: string;
};

function App() {
  const [status, setStatus] = useState<string>("loading...");
  const [products, setProducts] = useState<Product[]>([]);
  const [loadingProducts, setLoadingProducts] = useState<boolean>(false);
  const [form, setForm] = useState<{ name: string; description: string; price: string }>({
    name: "",
    description: "",
    price: ""
  });
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchHealth = () => {
    fetch("/api/health")
      .then((res) => res.json())
      .then((data) => setStatus(data.status ?? "unknown"))
      .catch(() => setStatus("error"));
  };

  const fetchProducts = () => {
    setLoadingProducts(true);
    setError(null);
    fetch("/api/products")
      .then((res) => {
        if (!res.ok) {
          throw new Error("加载商品失败");
        }
        return res.json() as Promise<Product[]>;
      })
      .then((data) => {
        setProducts(data);
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "未知错误");
      })
      .finally(() => setLoadingProducts(false));
  };

  useEffect(() => {
    fetchHealth();
    fetchProducts();
  }, []);

  const handleChange = (field: "name" | "description" | "price", value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) {
      setError("商品名称必填");
      return;
    }
    const priceNumber = Number(form.price);
    if (Number.isNaN(priceNumber) || priceNumber < 0) {
      setError("价格必须是非负数字");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/products", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          name: form.name.trim(),
          description: form.description.trim() || null,
          price: priceNumber
        })
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.message || "创建商品失败");
      }

      const created = (await res.json()) as Product;
      setProducts((prev) => [created, ...prev]);
      setForm({ name: "", description: "", price: "" });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "未知错误");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background:
          "radial-gradient(circle at top left, #4f46e5, transparent 55%), radial-gradient(circle at bottom right, #ec4899, transparent 55%), #020617",
        color: "white",
        fontFamily:
          "-apple-system, BlinkMacSystemFont, system-ui, -system-ui, sans-serif"
      }}
    >
      <div
        style={{
          backgroundColor: "rgba(15,23,42,0.9)",
          borderRadius: "24px",
          padding: "32px 40px",
          boxShadow:
            "0 24px 60px rgba(15,23,42,0.8), 0 0 0 1px rgba(148,163,184,0.2)",
          maxWidth: "480px",
          width: "100%"
        }}
      >
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            padding: "4px 10px",
            borderRadius: "999px",
            background:
              "linear-gradient(90deg, rgba(52,211,153,0.15), rgba(59,130,246,0.15))",
            fontSize: 12,
            color: "#a5b4fc",
            marginBottom: 16
          }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: "999px",
              backgroundColor: status === "ok" ? "#22c55e" : "#f97316",
              boxShadow:
                status === "ok"
                  ? "0 0 0 4px rgba(34,197,94,0.35)"
                  : "0 0 0 4px rgba(249,115,22,0.35)"
            }}
          />
          <span>Render Web Service Ready</span>
        </div>
        <h1
          style={{
            fontSize: 32,
            fontWeight: 700,
            letterSpacing: "-0.03em",
            marginBottom: 12
          }}
        >
          ShopHunter
        </h1>
        <p
          style={{
            fontSize: 14,
            color: "#cbd5f5",
            lineHeight: 1.6,
            marginBottom: 24
          }}
        >
          这是一个使用 Node.js + TypeScript 构建的全栈示例，后端提供
          API，前端使用 React + Vite 构建并由同一个 Node 服务静态托管，可直接在{" "}
          <span style={{ fontWeight: 600 }}>render.com</span> 上作为 Web
          Service 部署。
        </p>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
            gap: 16,
            marginBottom: 24
          }}
        >
          <div
            style={{
              padding: 12,
              borderRadius: 16,
              backgroundColor: "rgba(15,23,42,0.8)",
              border: "1px solid rgba(148,163,184,0.35)"
            }}
          >
            <div style={{ fontSize: 12, color: "#9ca3af", marginBottom: 4 }}>
              后端
            </div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>Express + TS</div>
            <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 4 }}>
              监听 <code style={{ fontSize: 12 }}>PORT</code> 环境变量。
            </div>
          </div>
          <div
            style={{
              padding: 12,
              borderRadius: 16,
              backgroundColor: "rgba(15,23,42,0.8)",
              border: "1px solid rgba(148,163,184,0.35)"
            }}
          >
            <div style={{ fontSize: 12, color: "#9ca3af", marginBottom: 4 }}>
              前端
            </div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>React + Vite</div>
            <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 4 }}>
              构建后静态文件由同一服务托管。
            </div>
          </div>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            fontSize: 12,
            color: "#9ca3af"
          }}
        >
          <span>
            API 健康状态：{" "}
            <span style={{ fontWeight: 600, color: "#e5e7eb" }}>{status}</span>
          </span>
          <span>GET /api/health</span>
        </div>

        <div
          style={{
            marginTop: 24,
            paddingTop: 20,
            borderTop: "1px solid rgba(148,163,184,0.35)",
            display: "grid",
            gap: 16
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 4
            }}
          >
            <h2
              style={{
                fontSize: 16,
                fontWeight: 600
              }}
            >
              商品列表（数据库）
            </h2>
            <button
              type="button"
              onClick={fetchProducts}
              style={{
                padding: "4px 10px",
                borderRadius: 999,
                border: "1px solid rgba(148,163,184,0.6)",
                backgroundColor: "rgba(15,23,42,0.9)",
                color: "#e5e7eb",
                fontSize: 11,
                cursor: "pointer"
              }}
            >
              重新加载
            </button>
          </div>

          {error && (
            <div
              style={{
                padding: "8px 10px",
                borderRadius: 8,
                backgroundColor: "rgba(248,113,113,0.12)",
                border: "1px solid rgba(248,113,113,0.6)",
                fontSize: 12,
                color: "#fecaca"
              }}
            >
              {error}
            </div>
          )}

          <form
            onSubmit={handleSubmit}
            style={{
              display: "grid",
              gap: 8,
              padding: 12,
              borderRadius: 16,
              backgroundColor: "rgba(15,23,42,0.8)",
              border: "1px solid rgba(148,163,184,0.35)"
            }}
          >
            <div style={{ display: "grid", gap: 6 }}>
              <label style={{ fontSize: 12, color: "#9ca3af" }}>
                名称（必填）
              </label>
              <input
                value={form.name}
                onChange={(e) => handleChange("name", e.target.value)}
                placeholder="例如：测试商品"
                style={{
                  width: "100%",
                  padding: "6px 8px",
                  borderRadius: 8,
                  border: "1px solid rgba(148,163,184,0.6)",
                  backgroundColor: "rgba(15,23,42,0.9)",
                  color: "#e5e7eb",
                  fontSize: 13
                }}
              />
            </div>

            <div style={{ display: "grid", gap: 6 }}>
              <label style={{ fontSize: 12, color: "#9ca3af" }}>描述</label>
              <textarea
                value={form.description}
                onChange={(e) => handleChange("description", e.target.value)}
                placeholder="可选，商品描述"
                rows={2}
                style={{
                  width: "100%",
                  padding: "6px 8px",
                  borderRadius: 8,
                  border: "1px solid rgba(148,163,184,0.6)",
                  backgroundColor: "rgba(15,23,42,0.9)",
                  color: "#e5e7eb",
                  fontSize: 13,
                  resize: "vertical"
                }}
              />
            </div>

            <div style={{ display: "grid", gap: 6 }}>
              <label style={{ fontSize: 12, color: "#9ca3af" }}>
                价格（必填，数字）
              </label>
              <input
                type="number"
                value={form.price}
                onChange={(e) => handleChange("price", e.target.value)}
                placeholder="例如：99.9"
                step="0.01"
                min="0"
                style={{
                  width: "100%",
                  padding: "6px 8px",
                  borderRadius: 8,
                  border: "1px solid rgba(148,163,184,0.6)",
                  backgroundColor: "rgba(15,23,42,0.9)",
                  color: "#e5e7eb",
                  fontSize: 13
                }}
              />
            </div>

            <button
              type="submit"
              disabled={saving}
              style={{
                marginTop: 6,
                padding: "8px 10px",
                borderRadius: 999,
                border: "none",
                background:
                  "linear-gradient(90deg, #4f46e5, #6366f1, #ec4899)",
                color: "white",
                fontSize: 13,
                fontWeight: 600,
                cursor: saving ? "default" : "pointer",
                opacity: saving ? 0.7 : 1
              }}
            >
              {saving ? "保存中..." : "添加商品并写入数据库"}
            </button>
          </form>

          <div
            style={{
              maxHeight: 220,
              overflow: "auto",
              padding: 8,
              borderRadius: 16,
              backgroundColor: "rgba(15,23,42,0.8)",
              border: "1px solid rgba(148,163,184,0.35)"
            }}
          >
            {loadingProducts ? (
              <div style={{ fontSize: 12, color: "#9ca3af" }}>加载中...</div>
            ) : products.length === 0 ? (
              <div style={{ fontSize: 12, color: "#9ca3af" }}>
                暂无商品，先在上面添加一条试试。
              </div>
            ) : (
              <ul
                style={{
                  listStyle: "none",
                  padding: 0,
                  margin: 0,
                  display: "grid",
                  gap: 8
                }}
              >
                {products.map((p) => (
                  <li
                    key={p.id}
                    style={{
                      padding: 8,
                      borderRadius: 12,
                      backgroundColor: "rgba(15,23,42,0.9)",
                      border: "1px solid rgba(148,163,184,0.35)",
                      display: "grid",
                      gap: 4,
                      fontSize: 12
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: 8
                      }}
                    >
                      <span
                        style={{
                          fontWeight: 600,
                          color: "#e5e7eb"
                        }}
                      >
                        {p.name}
                      </span>
                      <span
                        style={{
                          fontWeight: 600,
                          color: "#a5b4fc"
                        }}
                      >
                        ¥{p.price.toFixed(2)}
                      </span>
                    </div>
                    {p.description && (
                      <div style={{ color: "#9ca3af" }}>{p.description}</div>
                    )}
                    <div style={{ color: "#6b7280" }}>
                      ID: {p.id} · 创建时间:{" "}
                      {new Date(p.createdAt).toLocaleString()}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;

