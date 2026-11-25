# Benchmark & Observability Report — Day 14

**Họ tên:** Nguyễn Minh Quân  
**Ngày chạy:** 25/11/2026  
**Môi trường:** Windows, Python 3.14.4 trong `.venv` cho benchmark local, Docker Desktop 29.6.2 cho stack production. Agent v1/v2 chạy local trên cổng 18001/18002. Bản ghi này dùng số đo từ các lần chạy hỗ trợ bởi Codex.

## 1. SLO và quality gate

| Chỉ số | Ngưỡng |
|---|---:|
| p95 latency `/ask`, mặc định của `load_test.py` | ≤ 500 ms |
| Error rate `/ask`, mặc định của `load_test.py` | ≤ 2% |
| Accuracy, quality gate baseline | ≥ 80%, 0 regression nếu có baseline |
| Accuracy, Exercise 7.3 sau khi sửa KB | 100%, 0 regression |

## 2. Benchmark hiệu năng (develop)

### 2.1 Concurrency vs latency

Mỗi lần chạy gửi 300 request vào agent v2 với `MOCK_SLOW_RATE=0.03`, `MOCK_ERROR_RATE=0.01`.

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 4.47 | 201.9 | 233.4 | 1671.7 | 0.33% | PASS |
| 10 | 34.68 | 206.5 | 235.5 | 1716.4 | 0.67% | PASS |
| 50 | 117.69 | 211.8 | 272.8 | 1713.3 | 2.33% | FAIL |
| 100 | 52.64 | 401.9 | 3433.9 | 3926.2 | 2.00% | FAIL |

RPS tăng tới concurrency 50 rồi giảm ở 100. Tại 100, p95 cao hơn 3 giây. Phép đo một lần trên máy này cho thấy có điểm bão hòa trong cấu hình đã thử. Cần lặp lại hoặc xem tài nguyên để xác định nút thắt.

### 2.2 Tail latency

Mỗi lần chạy gửi 300 request ở concurrency 20, giữ `MOCK_ERROR_RATE=0.01`.

| `MOCK_SLOW_RATE` | Avg (ms) | p95 (ms) | p99 (ms) |
|---:|---:|---:|---:|
| 0 | 203.0 | 233.2 | 249.2 |
| 0.03 | 265.3 | 241.1 | 1710.1 |
| 0.1 | 355.1 | 1704.2 | 1729.8 |

Ở mức 0.03, p99 tăng hơn 1.4 giây so với mức 0, trong khi trung bình tăng 62.3 ms. Tại 0.1, nhóm request chậm chiếm đủ lớn để p95 cũng tăng mạnh.

## 3. Benchmark chất lượng (develop)

Tắt lỗi upstream ngẫu nhiên bằng `MOCK_ERROR_RATE=0` trong hai lần eval baseline để tập trung đo nội dung câu trả lời.

| Chỉ số | Agent v1 | Agent v2 | Agent v2 sau khi sửa KB |
|---|---:|---:|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | Chờ chạy |
| Avg tokens / câu | 56.8 | 109.1 | Chờ chạy |
| Tổng cost (USD) | 0.00039975 | 0.000762 | Chờ chạy |
| Cost / câu đúng (USD) | 0.00039975 | 0.00003627 | Chờ chạy |
| Quality gate baseline | FAIL | PASS, 0 regression | Chờ chạy |

| Câu v2 sai | Keyword thiếu theo `eval_v2.json` | Sửa KB |
|---|---|---|
| `security-02` | token, hết hạn, chữ ký | Cần bổ sung |
| `scaling-03` | cpu, memory, custom metrics | Cần bổ sung |

V2 dùng nhiều token hơn mỗi câu, đồng thời có chi phí trên mỗi câu đúng thấp hơn vì trả lời đúng 21 thay vì 1 câu. Chi phí là số ước tính của mock LLM. Latency của hai lượt eval chịu ảnh hưởng của request chậm ngẫu nhiên.

**Cần bổ sung** kết quả `eval_v2_fixed.json`, phần giải thích thay đổi KB và job CI hoặc cách dùng exit code để chặn merge.

## 4. Observability stack (production)

### 4.1 Dashboard và metrics

[Ảnh Grafana](screenshots/grafana-dashboard.png) ghi nhận **39.8 req/s**, **0.81% lỗi**, **p95 294.71 ms** và **3 instance up** tại thời điểm chụp. Gọi `GET /metrics` qua Nginx trả `404`. Prometheus scrape agent trực tiếp trong mạng Docker.

### 4.2 Thí nghiệm cảnh báo

Chạy Locust với 30 người dùng và tốc độ tăng 5 người dùng/giây, đặt hai biến lỗi mô phỏng cùng lúc. Thời gian dưới đây tính từ khi áp dụng cấu hình đến lần đầu API Prometheus trả về trạng thái `firing`.

| Cấu hình | Alert | Thời gian | Panel |
|---|---|---:|---|
| `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | 104 s | Error rate |
| `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | 161 s | Latency p95 |

[Ảnh trang Alerts](screenshots/prometheus-alert-firing.png) có cả hai alert ở trạng thái `firing` cùng lúc. `LLMCostBurnRateHigh` cũng đang firing trong ảnh và đã được quan sát trước khi áp dụng hai biến lỗi. `promtool test rules` trả `SUCCESS`.

### 4.3 Trace

Hai trace được chụp trong một lượt tải ngắn dùng cùng cấu hình lỗi mô phỏng.

- [Trace chậm](screenshots/jaeger-slow-trace.png) có ID `a2eef2bec06c24d4ed6a5705e011b634`. `POST /ask` mất 1712.89 ms. Span `chat mock-llm-small` chiếm 1687.67 ms (98.53% thời gian request).
- [Trace lỗi](screenshots/jaeger-error-trace.png) có ID `0e25cb84a61b835c62980884e7246dc1`. Span gọi model ghi event `exception`. Log agent ghi upstream mock trả `503`.

Dòng log JSON khớp với hai `trace_id` trên.

```json
{"ts":"2026-11-25T09:44:14.997474+00:00","level":"INFO","service":"observable-agent","instance":"151e3e702010","event":"llm_call","trace_id":"a2eef2bec06c24d4ed6a5705e011b634","span_id":"ef610f6692036003","request_id":"41fb93fd006b","model":"mock-llm-small","agent_version":"v2","input_tokens":74,"output_tokens":37,"cost_usd":3.3e-05,"llm_ms":1688.2}
{"ts":"2026-11-25T09:44:13.446758+00:00","level":"INFO","service":"observable-agent","instance":"151e3e702010","event":"llm_error","trace_id":"0e25cb84a61b835c62980884e7246dc1","span_id":"0be1750de4f39288","request_id":"2463a4b40fcf","error":"Upstream LLM error: 503 Service Unavailable (mock)"}
```

## 5. Benchmark scaling (production)

Lấy dòng `POST /ask` trong hai CSV. Hai lượt cùng chạy headless 100 người dùng, tăng 10 người dùng/giây trong 2 phút.

| Replica | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures | Error rate |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 60.05 | 190 | 230 | 1700 | 77 / 7192 | 1.07% |
| 3 | 59.86 | 190 | 220 | 1700 | 61 / 7165 | 0.85% |

Trong phép đo này, tăng lên 3 replica làm p95 giảm 10 ms, p99 giữ ở 1700 ms và RPS gần như giữ nguyên. Hai lượt đo có cùng cấu hình mock LLM, gồm các request chậm mô phỏng. Có thể dùng Jaeger và metric LLM để kiểm tra phần thời gian đến từ span gọi model.

## 6. Kết luận

**Cần bổ sung** nhận xét của học viên về SLO, trace và alert dựa trên kết quả thực nghiệm.
