# Deployment Information

## Public URL

https://k5-l3a-day14-nguyenminhquan-2a202603510-deployme-production.up.railway.app

## Platform

Railway · project `comfortable-miracle` · environment `production`. Bản deploy dùng thư mục `06-lab-complete/` làm gốc upload, build bằng Dockerfile của agent. Redis chạy trong cùng project.

[Railway deployment](https://railway.com/project/d2d9711c-57df-4b45-8edf-8c68558012cd/service/b20096d1-cf25-4575-9b28-ddcc6a5052bc?id=b350d1ca-ecec-4d3f-820b-e931ed005e65)

## Environment variables

| Biến | Cấu hình |
|---|---|
| `PORT` | Railway tự cấp |
| `REDIS_URL` | Tham chiếu riêng `${{Redis.REDIS_URL}}` |
| `AGENT_API_KEY` | Giá trị lưu trong Railway Variables |
| `ENVIRONMENT` | `production` |

## Kiểm tra CP6

Chạy trong Bash. Nhập API key ở dòng `read` để giữ giá trị trong phiên terminal.

```bash
BASE='https://k5-l3a-day14-nguyenminhquan-2a202603510-deployme-production.up.railway.app'
read -rsp 'Agent API key: ' AGENT_API_KEY
printf '\n'

curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -d '{"question":"What is Docker?"}'
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"What is Docker?"}'
unset AGENT_API_KEY
```

| Request | Kết quả thực tế |
|---|---:|
| `GET /health` | 200 |
| `GET /ready` | 200 |
| `POST /ask` thiếu API key | 401 |
| `POST /ask` có API key hợp lệ | 200 |

Request có key trả JSON chứa trường `answer`.

## Ảnh deploy

- [Dashboard Railway với agent và Redis online](screenshots/dashboard.png)
- [Deployment đang chạy](screenshots/running.png)
- [Kết quả bốn request CP6 trong Railway Network Logs](screenshots/test.png)
