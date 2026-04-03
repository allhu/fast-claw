import express from "express";
import path from "path";
import cors from "cors";
import { PrismaClient } from "@prisma/client";
import { PrismaLibSQL } from "@prisma/adapter-libsql";

const app = express();
const port = process.env.PORT || 3000;

const nodeEnv = process.env.NodeEnv ?? "local";

let prisma: PrismaClient;

if (nodeEnv === "local") {
  // 本地开发：使用本地 SQLite（DATABASE_URL 通常为 file:./dev.db）
  prisma = new PrismaClient();
} else {
  // 线上(prod)：使用 Turso + libSQL adapter（Prisma 7 官方推荐写法）
  const tursoUrl = process.env.DATABASE_URL;
  const tursoToken = process.env.DATABASE_AUTH_TOKEN;

  if (!tursoUrl) {
    throw new Error("DATABASE_URL 未配置（Turso URL）");
  }

  const adapter = new PrismaLibSQL({
    url: tursoUrl,
    authToken: tursoToken
  });

  prisma = new PrismaClient({ adapter });
}

app.use(cors());
app.use(express.json());

app.get("/api/health", async (_req, res) => {
  try {
    await prisma.$queryRaw`SELECT 1`;
    res.json({ status: "ok", db: "ok", env: nodeEnv });
  } catch (e) {
    res.status(500).json({ status: "error", db: "error", env: nodeEnv });
  }
});

app.get("/api/products", async (_req, res) => {
  const products = await prisma.product.findMany({
    orderBy: { createdAt: "desc" },
    take: 10
  });
  res.json(products);
});

app.post("/api/products", async (req, res) => {
  const { name, description, price } = req.body;
  if (!name || typeof price !== "number") {
    return res.status(400).json({ message: "name 和 price 必填" });
  }

  const product = await prisma.product.create({
    data: { name, description, price }
  });

  res.status(201).json(product);
});

const clientDistPath = path.join(__dirname, "..", "..", "client", "dist");
app.use(express.static(clientDistPath));

app.get("*", (_req, res) => {
  res.sendFile(path.join(clientDistPath, "index.html"));
});

app.listen(port, () => {
  // eslint-disable-next-line no-console
  console.log(`Server listening on port ${port}`);
});

