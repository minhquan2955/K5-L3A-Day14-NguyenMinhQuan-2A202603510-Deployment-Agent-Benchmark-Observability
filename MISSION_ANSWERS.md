# Day 14 Lab - Mission Answers

Ngày chạy thử: 25/11/2026.

## CP0 — Môi trường

`docker run --rm hello-world` in `Hello from Docker!`. Docker Desktop chạy phiên bản 29.6.2. Docker Hub trả HTTP 429 trong lượt tải đầu nên dùng image cùng tag qua mirror công khai. Ubuntu chạy WSL2 và có Python 3.14.4. Lần kiểm tra WSL2 còn thiếu pip và Docker integration. Các bài local dùng `.venv` trên Windows. Phép thử SIGTERM Part 5 dùng Python trong container Linux.

## Part 1 — Localhost vs Production

### Exercise 1.1 — Anti-patterns

1. `develop/app.py:17–18` đặt API key và chuỗi kết nối có mật khẩu trực tiếp trong code. Giá trị nhạy cảm có thể lọt vào lịch sử Git.
2. `develop/app.py:21–22` cố định chế độ debug và giới hạn token. Đổi môi trường cần sửa code.
3. `develop/app.py:33–38` dùng `print()` và ghi cả key. Điều này làm lộ thông tin nhạy cảm và khó lọc log theo mức độ hay sự kiện.
4. `develop/app.py:40–44` thiếu endpoint health check. Nền tảng thiếu tín hiệu để phát hiện và khởi động lại process có lỗi.
5. `develop/app.py:51–53` bind `localhost`, cố định cổng `8000` và bật reload. Container cần lắng nghe trên giao diện phù hợp và dùng cổng được cấp.

### Exercise 1.2 — Gọi API develop

Gọi API trên cổng thử nghiệm `18000` để tránh xung đột với các bài khác.

```text
POST /ask?question=Hello → HTTP 200
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
GET /health (bản production) → HTTP 200
```

### Exercise 1.3 — So sánh develop và production

| Hạng mục | Develop | Production | Vì sao quan trọng |
|---|---|---|---|
| Cấu hình | Hằng số trong code | `production/config.py` đọc biến môi trường | Dùng cùng code cho nhiều môi trường và giữ secret ngoài repo |
| Health check | Thiếu route | `production/app.py:135` có `GET /health` | Nền tảng có thể kiểm tra tình trạng process |
| Logging | `print()`, có ghi key | Dùng `logging` và cấu hình mức log | Dễ lọc theo mức độ, theo dõi sự kiện và tránh ghi secret |
| Shutdown | Thiếu hook vòng đời để dọn tài nguyên | FastAPI `lifespan` quản lý startup và shutdown | Có chỗ giải phóng tài nguyên khi process dừng |
| Cổng và reload | Cố định cổng, luôn reload | Cổng từ `PORT`, reload theo `DEBUG` | Chạy được trên môi trường cấp cổng động và kiểm soát reload |

## Part 2 — Docker

### Exercise 2.1 — Dockerfile

1. Base image là `python:3.11`.
2. Working directory là `/app`.
3. Copy `requirements.txt` trước khi cài thư viện để Docker tái sử dụng layer cài dependencies khi chỉ sửa mã nguồn.
4. `ENTRYPOINT` đặt chương trình chính của container. `CMD` đặt lệnh mặc định khi dùng riêng, hoặc đối số mặc định cho `ENTRYPOINT` khi dùng cùng.

### Exercise 2.2 — Build và chạy container

Container develop dùng cổng host `18080`. `POST /ask?question=Hello` trả `HTTP/1.1 200 OK` và có trường `answer`.

### Exercise 2.3 — Kích thước image

| Image | `docker image ls my-agent` | `docker image inspect` |
|---|---:|---:|
| `my-agent:develop` | 1.67 GB | 426320089 byte |
| `my-agent:advanced` | 240 MB | 57409166 byte |

Theo số byte từ `docker image inspect`, image advanced nhỏ hơn **86.53%**. Cùng một cách đo được dùng cho cả hai image.

### Exercise 2.4 — Stack Docker Compose

```text
Client → Nginx → Agent
                 ├─ phụ thuộc Redis
                 └─ phụ thuộc Qdrant
```

Redis và Qdrant báo healthy khi agent khởi động. Qua Nginx, `GET /health` trả `200` và `POST /ask` với JSON `{"question":"Hello"}` trả lời thành công. Cổng host `80` đã được sử dụng nên lượt chạy dùng mapping tạm `127.0.0.1:18081 → 80`.

## Part 3 — Cloud Deployment

### Exercise 3.1 — Railway

Agent Part 6 đã có `railway.toml` dùng Dockerfile và health check tại `/health`. **Trạng thái:** chưa deploy. URL public, ảnh deploy và kết quả bốn request CP6 sẽ được bổ sung sau khi dịch vụ chạy trên Railway với Redis.

### Exercise 3.2 — So sánh Railway và Render

| Hạng mục | Railway trong Part 6 | Render trong mẫu Part 3 |
|---|---|---|
| Đóng gói | `builder = "DOCKERFILE"`; lệnh khởi động nằm trong Dockerfile | Blueprint dùng runtime Python, khai báo `buildCommand` và `startCommand` |
| Health check | `healthcheckPath = "/health"` | `healthCheckPath: /health` |
| Dịch vụ và biến môi trường | Khai báo Redis và đặt `AGENT_API_KEY`, `REDIS_URL` trên nền tảng | Blueprint có thể khai báo thêm Redis, sinh giá trị key hoặc yêu cầu nhập trên dashboard |

Railway dùng cấu hình build và deploy cho agent. Blueprint Render mô tả các service của cả stack trong một file.

### Exercise 3.3 — Pipeline Cloud Run

1. Cloud Build cài dependencies và chạy `pytest`.
2. Bước build tạo Docker image với tag theo commit SHA và `latest`.
3. Bước push đẩy cả hai tag lên registry, rồi bước deploy dùng image theo commit SHA.
4. Cloud Run cấu hình tài nguyên, giới hạn số instance và lấy secret từ Secret Manager. `service.yaml` mô tả cấu hình service theo dạng khai báo.

## Part 4 — API Security

### Exercise 4.1–4.3 — Kết quả kiểm tra

Gửi JSON `{"question":"Hello"}` đến `POST /ask` trên các app mẫu local. Dưới đây là mã HTTP đo được. Token được giữ trong bộ nhớ của client khi chạy thử.

| Bản | Request | HTTP |
|---|---|---:|
| Develop | Thiếu `X-API-Key` | 401 |
| Develop | Có `X-API-Key` hợp lệ | 200 |
| Production | 10 request đầu với JWT của tài khoản demo `student` | 200 |
| Production | Request thứ 11 trong cùng cửa sổ rate limit | 429 |

Trích output `curl -i`, giữ mã HTTP, `Retry-After` và response body:

```text
HTTP/1.1 401 Unauthorized
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

HTTP/1.1 200 OK
{"question":"Hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}

HTTP/1.1 429 Too Many Requests
retry-after: 59
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

### Exercise 4.4 — Cost guard

Dùng khóa Redis theo `user_id` và tháng UTC. Ước tính chi phí từ input/output token và giá model. Chỉ chấp nhận nếu tổng chi tiêu cộng chi phí dự kiến còn trong ngân sách 10 USD/tháng. Thực hiện kiểm tra và cập nhật trong cùng thao tác nguyên tử để hai request đồng thời không cùng dùng phần ngân sách còn lại. Khi vượt ngưỡng, trả `402`. Sang tháng mới, hệ thống dùng khóa tháng mới và Redis tự dọn khóa cũ theo TTL.

## Part 5 — Scaling & Reliability

### Exercise 5.1–5.2 — Health check và graceful shutdown

App mẫu develop trả HTTP `200` ở cả `/health` và `/ready`. Response `/health` có `status: degraded` khi phép đo RAM tại thời điểm chạy là `97.7%`. Response `/ready` có `ready: true`.

`/health` cho biết process đang hoạt động. `/ready` cho biết ứng dụng đã sẵn sàng nhận traffic. Thử trong container Linux, khi gửi SIGTERM lúc `POST /ask` đang xử lý, request vẫn trả `200`, process thoát mã `0` và log có `Shutdown complete`.

### Exercise 5.3–5.5 — Stateless, load balancing và session

Nginx phân phối request qua các replica. Mỗi replica đọc và ghi lịch sử bằng cùng khóa `session:<session_id>` trong Redis. Vì vậy, request kế tiếp có thể vào replica khác và vẫn đọc được toàn bộ lịch sử. Khi lưu lịch sử riêng trong RAM từng process, mỗi replica chỉ thấy phần lịch sử nó đã xử lý.

```text
Total requests: 5
Instances used: {'instance-e46abc', 'instance-6a84d2', 'instance-274621'}
Total messages: 10
Session history preserved across all instances via Redis!
```

Lượt đầu gặp HTTP `502` khi Nginx đã mở cổng nhưng agent còn khởi động. Lượt chạy trên dùng `docker compose up --wait --scale agent=3`.

## Part 6 — Final Project

Checker gốc được chạy đầy đủ trong môi trường Linux với Python 3.11, Docker và Redis tạm. Image runtime có kích thước 63 MB theo checker. Khi gửi SIGTERM, request đang xử lý vẫn trả `200` và process thoát mã `0`. `docker stop` hoàn tất trong 0,4 giây.

```text
📋 Checklist Deliverable
   ✅ Dockerfile (multi-stage, < 500 MB)
   ✅ docker-compose.yml (agent + redis)
   ✅ .dockerignore
   ✅ Health check endpoint (GET /health)
   ✅ Readiness endpoint (GET /ready)
   ✅ API Key authentication
   ✅ Rate limiting
   ✅ Cost guard
   ✅ Config từ environment variables
   ✅ Structured logging
   ✅ Graceful shutdown
   ✅ Public URL ready (Railway / Render config)
Result: 12/12 tiêu chí đạt · 41/41 checks passed
🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

## AI log

| Yêu cầu | Trợ giúp đã dùng | Học viên tự sửa và kiểm tra |
|---|---|---|
| Chia lab và rà soát câu trả lời theo checklist | Hỗ trợ đối chiếu tài liệu K5, chạy bài mẫu và ghi lại kết quả thực nghiệm. | Chưa ghi nhận lượt tự kiểm chứng. |
| Chẩn đoán lỗi khởi động stack observability | Hỗ trợ tái hiện lỗi `ModuleNotFoundError: uvicorn` và chỉnh `PYTHONUSERBASE` trong Dockerfile Part 7. | Chưa ghi nhận lượt tự kiểm chứng. |
| Hoàn thiện Part 6 | Hỗ trợ trực tiếp triển khai agent, Redis, Docker, Compose và cấu hình Railway. Checker gốc báo 12/12 trong lượt kiểm tra trên Linux. | Chưa ghi nhận lượt tự kiểm chứng. |
