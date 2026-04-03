import React, { useEffect, useState } from "react";

function App() {
  const [status, setStatus] = useState<string>("loading...");

  useEffect(() => {
    fetch("/api/health")
      .then((res) => res.json())
      .then((data) => setStatus(data.status ?? "unknown"))
      .catch(() => setStatus("error"));
  }, []);

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
      </div>
    </div>
  );
}

export default App;

