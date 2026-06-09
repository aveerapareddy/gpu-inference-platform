import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8080';
const API_KEY = __ENV.BENCHMARK_API_KEY || 'test-key';
const MODEL = __ENV.BENCHMARK_MODEL || 'demo';
const PROMPT = __ENV.BENCHMARK_PROMPT || 'Summarize GPU batching in one sentence.';
const MAX_TOKENS = Number(__ENV.BENCHMARK_MAX_TOKENS || 32);
const STREAM = (__ENV.BENCHMARK_STREAM || 'false') === 'true';

export const options = {
  scenarios: {
    benchmark: {
      executor: 'shared-iterations',
      vus: Number(__ENV.BENCHMARK_VUS || 1),
      iterations: Number(__ENV.BENCHMARK_ITERATIONS || 1),
      maxDuration: __ENV.BENCHMARK_MAX_DURATION || '2m',
    },
  },
  thresholds: {
    http_req_failed: ['rate<1'],
  },
};

export default function () {
  const payload = JSON.stringify({
    model: MODEL,
    messages: [{ role: 'user', content: PROMPT }],
    max_tokens: MAX_TOKENS,
    stream: STREAM,
  });

  const params = {
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      'Content-Type': 'application/json',
    },
    tags: { scenario: __ENV.BENCHMARK_SCENARIO || 'k6' },
  };

  const res = http.post(`${BASE_URL}/v1/chat/completions`, payload, params);
  check(res, {
    'status is 200': (r) => r.status === 200,
  });
  sleep(0.1);
}
