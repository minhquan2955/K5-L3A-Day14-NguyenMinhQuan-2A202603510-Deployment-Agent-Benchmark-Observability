# Benchmark & Observability Report — Day 14

**Họ tên:** Nguyễn Minh Quân  
**Ngày chạy:** 25/11/2026  
**Môi trường:** Windows, Python 3.14.4 trong `.venv` cho benchmark local, Docker Desktop 29.6.2 cho stack production. Agent v1/v2 chạy local trên cổng 18001/18002. Các phép đo hiệu năng và observability dùng cấu hình baseline. Lần eval cuối dùng knowledge base đã cập nhật trong `develop/`.

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

p50, p95 và p99 là các ngưỡng mà lần lượt khoảng 50%, 95% và 99% request hoàn tất trong thời gian đó. Với SLO 500 ms và 2% lỗi, concurrency 50 vượt ngưỡng lỗi, còn concurrency 100 vượt ngưỡng p95.

### 2.2 Tail latency

Mỗi lần chạy gửi 300 request ở concurrency 20, giữ `MOCK_ERROR_RATE=0.01`.

| `MOCK_SLOW_RATE` | Avg (ms) | p95 (ms) | p99 (ms) |
|---:|---:|---:|---:|
| 0 | 203.0 | 233.2 | 249.2 |
| 0.03 | 265.3 | 241.1 | 1710.1 |
| 0.1 | 355.1 | 1704.2 | 1729.8 |

Ở mức 0.03, p99 tăng hơn 1.4 giây so với mức 0, trong khi trung bình tăng 62.3 ms. Tại 0.1, nhóm request chậm chiếm đủ lớn để p95 cũng tăng mạnh.

## 3. Benchmark chất lượng (develop)

Tắt lỗi upstream ngẫu nhiên bằng `MOCK_ERROR_RATE=0` trong các lần eval để tập trung đo nội dung câu trả lời. Lần chạy cuối so sánh với `reports/eval_v2.json` và lưu vào [eval_v2_fixed.json](reports/eval_v2_fixed.json).

| Chỉ số | Agent v1 | Agent v2 | Agent v2 sau khi sửa KB |
|---|---:|---:|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100% (23/23) |
| Avg tokens / câu | 56.8 | 109.1 | 114.0 |
| Tổng cost (USD) | 0.00039975 | 0.000762 | 0.000793 |
| Cost / câu đúng (USD) | 0.00039975 | 0.00003627 | 0.00003449 |
| Quality gate | FAIL | PASS, 0 regression | PASS ở ngưỡng 100%, 0 regression |

| Câu v2 sai | Keyword thiếu theo `eval_v2.json` | Sửa KB |
|---|---|---|
| `security-02` | token, hết hạn, chữ ký | Bổ sung tài liệu về khác biệt giữa API key và JWT, gồm kiểm tra chữ ký và thời hạn của token |
| `scaling-03` | cpu, memory, custom metrics | Bổ sung tài liệu về chỉ số mà Kubernetes HPA dùng để điều chỉnh số pod |

V2 dùng nhiều token hơn mỗi câu, đồng thời có chi phí trên mỗi câu đúng thấp hơn vì trả lời được nhiều câu hơn. Sau khi bổ sung hai tài liệu, tổng chi phí ước tính tăng từ 0.000762 lên 0.000793 USD, còn chi phí trên mỗi câu đúng giảm từ 0.00003627 xuống 0.00003449 USD. Các giá trị này là ước tính của mock LLM. Latency eval chịu ảnh hưởng của tỷ lệ request chậm ngẫu nhiên, nên dùng phép đo tải ở mục 2 để đánh giá độ trễ.

### Quality gate trong CI

Trong job chạy ở thư mục `develop/`, khởi động agent với `AGENT_VERSION=v2` và `MOCK_ERROR_RATE=0`, chờ `/health` trả `200`, rồi chạy:

```bash
python eval/run_eval.py --url http://localhost:8000 --min-accuracy 0.85 \
  --baseline "$BASELINE_REPORT" --out /tmp/eval-ci.json
```

`BASELINE_REPORT` trỏ tới JSON đã được chấp nhận trên nhánh đích. Exit code `1` làm job thất bại nếu accuracy dưới 85% hoặc có câu đúng ở baseline trở thành sai. Đặt job là required status check của nhánh đích để chặn merge. Lần kiểm tra cuối cho bài nộp dùng ngưỡng `1.0`.

## 4. Observability stack (production)

### 4.1 Dashboard và metrics

Exercise 7.1 ghi nhận ba loại metric trong app local:

- **Counter** `http_requests_total` đếm request theo method, route và HTTP status.
- **Gauge** `agent_in_flight_requests` tăng khi bắt đầu và giảm khi request kết thúc.
- **Histogram** `agent_question_length_chars` chia độ dài câu hỏi vào bucket. Với một câu thử 40 ký tự, `_count` tăng 1 và `_sum` tăng 40.

Label `route` dùng mẫu route cố định và nhóm URL không khớp thành `unmatched`. Nếu dùng URL thô, mỗi đường dẫn ngẫu nhiên do bot gửi có thể tạo thêm time series và làm tăng chi phí lưu trữ, bộ nhớ và truy vấn.

[Ảnh Grafana](screenshots/grafana-dashboard.png) ghi nhận **39.8 req/s**, **0.81% lỗi**, **p95 294.71 ms** và **3 instance up** tại thời điểm chụp. Gọi `GET /metrics` qua Nginx trả `404`. Prometheus scrape agent trực tiếp trong mạng Docker.

Để trả lời Exercise 7.4, đo riêng bằng các truy vấn PromQL của dashboard khi có 2 replica, Locust chạy 30 users và tăng 5 users/giây.

| Chỉ số | Kết quả |
|---|---:|
| p95 `POST /ask` | 292.72 ms |
| Avg `POST /ask` | 230.76 ms |
| Request/s theo instance | 4.99 và 4.97 |
| Input tokens/s | 738.62 |
| Output tokens/s | 392.01 |

p95 cao hơn avg khoảng 62 ms tại thời điểm đo. Nginx chia tải gần đều giữa hai replica theo request/s. Input tokens/s cao hơn vì prompt chứa câu hỏi và ngữ cảnh truy xuất, trong khi output chỉ gồm câu trả lời.

### 4.2 Thí nghiệm cảnh báo

Chạy Locust với 30 người dùng và tốc độ tăng 5 người dùng/giây, đặt hai biến lỗi mô phỏng cùng lúc. Thời gian dưới đây tính từ khi áp dụng cấu hình đến lần đầu API Prometheus trả về trạng thái `firing`.

| Cấu hình | Alert | Thời gian | Panel |
|---|---|---:|---|
| `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | 104 s | Error rate |
| `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | 161 s | Latency p95 |

[Ảnh trang Alerts](screenshots/prometheus-alert-firing.png) có cả hai alert ở trạng thái `firing` cùng lúc. `LLMCostBurnRateHigh` cũng đang firing trong ảnh và đã được quan sát trước khi áp dụng hai biến lỗi. `promtool test rules` trả `SUCCESS`.

Khi thay v2 bằng v1, HTTP vẫn có thể trả `200` dù câu trả lời thiếu nội dung. Để phát hiện, chạy eval golden dataset trước merge và định kỳ sau deploy. Theo dõi accuracy hoặc số câu bị regression như một chỉ số chất lượng riêng.

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

1. SLO theo percentile bắt được phần đuôi mà trung bình dễ che khuất. Với tỷ lệ request chậm 3%, p99 đã vượt 1,7 giây trong khi p95 chỉ 241,1 ms.
2. Trace cho biết phần nào của request chiếm thời gian. Trong trace chậm quan sát được, span gọi model chiếm 98,53% thời gian.
3. Alert hạ tầng báo lỗi và độ trễ. Eval chất lượng phát hiện câu trả lời sai dù API vẫn trả thành công.

Khi chạy production, theo dõi thêm tỷ lệ `502/504` tại Nginx để phát hiện các lỗi mà client đã nhận trước khi agent có thể ghi trạng thái.
