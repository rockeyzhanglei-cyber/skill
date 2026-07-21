# Spark 框架 API 参考

> 所有 API 必须从 `spark` 导入，禁止从 `vue`、`vue-router`、`pinia` 等原始库导入。

## 目录

- [响应式 API](#响应式-api)
- [路由 API](#路由-api)
- [状态管理 API](#状态管理-api)
- [HTTP 请求 API](#http-请求-api)
- [工具函数 API](#工具函数-api)
- [国际化 API](#国际化-api)
- [微前端 API](#微前端-api)
- [事件总线 API](#事件总线-api)

---

## 响应式 API

```typescript
import {
  ref,
  reactive,
  computed,
  watch,
  watchEffect,
  onMounted,
  onBeforeMount,
  onBeforeUnmount,
  onUnmounted,
  nextTick,
  toRef,
  toRefs,
  provide,
  inject
} from 'spark';
```

### ref

用于创建基本类型或对象的响应式引用。

```typescript
// 基本类型
const count = ref(0);
const message = ref<string>('');

// 对象类型
const user = ref<User | null>(null);

// 数组类型
const list = ref<User[]>([]);

// 访问和修改
count.value = 1;
console.log(count.value);
```

### reactive

用于创建对象的响应式代理。

```typescript
interface FormState {
  name: string;
  age: number;
  email: string;
}

const form = reactive<FormState>({
  name: '',
  age: 0,
  email: ''
});

// 直接访问，无需 .value
form.name = '张三';
console.log(form.name);
```

### computed

计算属性。

```typescript
const firstName = ref('张');
const lastName = ref('三');

// 只读计算属性
const fullName = computed(() => `${firstName.value}${lastName.value}`);

// 可写计算属性
const fullNameWritable = computed({
  get: () => `${firstName.value}${lastName.value}`,
  set: (value) => {
    firstName.value = value.charAt(0);
    lastName.value = value.slice(1);
  }
});
```

### watch

侦听器。

```typescript
// 侦听 ref
watch(count, (newVal, oldVal) => {
  console.log(`count 从 ${oldVal} 变为 ${newVal}`);
});

// 侦听 reactive 对象的属性
watch(() => form.name, (newVal) => {
  console.log(`name 变为 ${newVal}`);
});

// 侦听多个源
watch([firstName, lastName], ([newFirst, newLast]) => {
  console.log(`姓名: ${newFirst}${newLast}`);
});

// 立即执行
watch(count, (val) => {
  console.log(val);
}, { immediate: true });

// 深度侦听
watch(form, (val) => {
  console.log('form 变化了');
}, { deep: true });
```

### watchEffect

自动追踪依赖的侦听器。

```typescript
const stop = watchEffect(() => {
  // 自动追踪 firstName 和 lastName
  console.log(`姓名: ${firstName.value}${lastName.value}`);
});

// 停止侦听
stop();
```

### 生命周期钩子

```typescript
onMounted(() => {
  console.log('组件已挂载');
  // DOM 操作、API 请求等
});

onBeforeMount(() => {
  console.log('组件挂载前');
});

onBeforeUnmount(() => {
  console.log('组件卸载前');
  // 清理定时器、事件监听等
});

onUnmounted(() => {
  console.log('组件已卸载');
});
```

---

## 路由 API

> 注意：本项目采用无路由模式，路由 API 应谨慎使用。

```typescript
import { useRouter, useRoute } from 'spark';
```

### useRouter

```typescript
const router = useRouter();

// 编程式导航（无路由模式下不推荐）
// router.push('/user');
// router.replace('/user');
// router.go(-1);
```

### useRoute

```typescript
const route = useRoute();

// 获取路由参数
console.log(route.params);
console.log(route.query);
```

---

## 状态管理 API

```typescript
import { defineStore, storeToRefs } from 'spark';
```

### defineStore

定义 Store。

```typescript
// Option Store
export const useUserStore = defineStore('user', {
  state: () => ({
    userInfo: null as User | null,
    token: '',
    isLoggedIn: false
  }),

  getters: {
    displayName: (state) => state.userInfo?.name || '游客',
    isAdmin: (state) => state.userInfo?.role === 'admin'
  },

  actions: {
    async login(credentials: LoginParams) {
      const res = await request.post('/api/login', credentials);
      this.token = res.token;
      this.userInfo = res.user;
      this.isLoggedIn = true;
    },

    logout() {
      this.token = '';
      this.userInfo = null;
      this.isLoggedIn = false;
    },

    updateUserInfo(info: Partial<User>) {
      if (this.userInfo) {
        Object.assign(this.userInfo, info);
      }
    }
  }
});
```

### Setup Store

```typescript
export const useCounterStore = defineStore('counter', () => {
  // state
  const count = ref(0);

  // getters
  const doubleCount = computed(() => count.value * 2);

  // actions
  function increment() {
    count.value++;
  }

  function decrement() {
    count.value--;
  }

  async function fetchCount() {
    const res = await request.get('/api/count');
    count.value = res.data;
  }

  return {
    count,
    doubleCount,
    increment,
    decrement,
    fetchCount
  };
});
```

### 在组件中使用

```typescript
import { useUserStore } from '@/stores/user';
import { storeToRefs } from 'spark';

const userStore = useUserStore();

// 解构响应式状态（使用 storeToRefs）
const { userInfo, isLoggedIn } = storeToRefs(userStore);

// 直接访问 getters
console.log(userStore.displayName);

// 调用 actions
userStore.login({ username: 'admin', password: '123456' });

// 直接修改 state
userStore.token = 'new-token';

// 批量修改 state
userStore.$patch({
  token: 'new-token',
  isLoggedIn: true
});
```

---

## HTTP 请求 API

```typescript
import { request } from 'spark';
```

### 基本用法

```typescript
// GET 请求
const userList = await request.get<User[]>('/api/users');

// GET 带参数
const userDetail = await request.get<User>(`/api/users/${id}`);

// GET 带 query 参数
const searchResult = await request.get<User[]>('/api/users', {
  params: { name: '张三', status: 'active' }
});

// POST 请求
const newUser = await request.post<User>('/api/users', {
  name: '张三',
  email: 'zhangsan@example.com'
});

// PUT 请求
const updatedUser = await request.put<User>(`/api/users/${id}`, {
  name: '李四'
});

// DELETE 请求
await request.delete(`/api/users/${id}`);
```

### 封装 API 模块

```typescript
// src/views/User/apis/user.ts
import { request } from 'spark';
import type { User, UserQuery, UserDTO } from '../types/user';

export const userApi = {
  // 获取用户列表
  getList: (params?: UserQuery) =>
    request.get<PageResult<User>>('/api/users', { params }),

  // 获取用户详情
  getById: (id: number | string) =>
    request.get<User>(`/api/users/${id}`),

  // 创建用户
  create: (data: UserDTO) =>
    request.post<User>('/api/users', data),

  // 更新用户
  update: (id: number | string, data: Partial<UserDTO>) =>
    request.put<User>(`/api/users/${id}`, data),

  // 删除用户
  delete: (id: number | string) =>
    request.delete(`/api/users/${id}`),

  // 批量删除
  batchDelete: (ids: number[]) =>
    request.post('/api/users/batch-delete', { ids })
};
```

### 在组合式函数中使用

```typescript
// src/views/User/composables/useUserList.ts
import { ref, onMounted } from 'spark';
import { userApi } from '../apis/user';
import type { User } from '../types/user';

export function useUserList() {
  const loading = ref(false);
  const userList = ref<User[]>([]);
  const total = ref(0);

  const fetchList = async (params?: UserQuery) => {
    loading.value = true;
    try {
      const res = await userApi.getList(params);
      userList.value = res.data;
      total.value = res.total;
    } finally {
      loading.value = false;
    }
  };

  onMounted(() => {
    fetchList();
  });

  return {
    loading,
    userList,
    total,
    fetchList
  };
}
```

---

## 工具函数 API

```typescript
import { utils } from 'spark';
```

### 对象工具 (utils.object)

```typescript
// 深拷贝
const cloned = utils.object.cloneDeep(original);

// 选择属性
const picked = utils.object.pick(obj, ['name', 'age']);

// 忽略属性
const omitted = utils.object.omit(obj, ['password']);

// 合并对象
const merged = utils.object.merge({}, obj1, obj2);

// 检查是否为空对象
const isEmpty = utils.object.isEmpty(obj);
```

### 数组工具 (utils.array)

```typescript
// 分块
const chunks = utils.array.chunk([1, 2, 3, 4, 5], 2);
// [[1, 2], [3, 4], [5]]

// 去重
const unique = utils.array.uniq([1, 1, 2, 2, 3]);
// [1, 2, 3]

// 按属性去重
const uniqueBy = utils.array.uniqBy(users, 'id');

// 排序
const sorted = utils.array.sortBy(users, ['age'], ['desc']);

// 分组
const grouped = utils.array.groupBy(users, 'department');

// 扁平化
const flattened = utils.array.flatten([[1, 2], [3, 4]]);
// [1, 2, 3, 4]

// 查找索引
const index = utils.array.findIndex(users, { id: 1 });
```

### 日期工具 (utils.date)

```typescript
// 获取 dayjs 实例
const now = utils.date.dayjs();

// 格式化
const formatted = utils.date.dayjs().format('YYYY-MM-DD HH:mm:ss');

// 解析
const parsed = utils.date.dayjs('2024-01-01', 'YYYY-MM-DD');

// 操作
const tomorrow = utils.date.dayjs().add(1, 'day');
const lastMonth = utils.date.dayjs().subtract(1, 'month');
const startOfMonth = utils.date.dayjs().startOf('month');
const endOfMonth = utils.date.dayjs().endOf('month');

// 比较
const isAfter = utils.date.dayjs('2024-02-01').isAfter('2024-01-01');
const isBefore = utils.date.dayjs('2024-01-01').isBefore('2024-02-01');
const isSame = utils.date.dayjs('2024-01-01').isSame('2024-01-01');

// 差值
const diffDays = utils.date.dayjs('2024-02-01').diff('2024-01-01', 'day');
```

### Cookie 工具 (utils.cookie)

```typescript
// 设置 Cookie
utils.cookie.set('token', 'abc123', { expires: 7 }); // 7 天后过期

// 获取 Cookie
const token = utils.cookie.get('token');

// 删除 Cookie
utils.cookie.remove('token');

// 检查 Cookie 是否存在
const hasToken = utils.cookie.has('token');
```

### Base64 工具 (utils.base64)

```typescript
// 编码
const encoded = utils.base64.encode('Hello World');
// "SGVsbG8gV29ybGQ="

// 解码
const decoded = utils.base64.decode('SGVsbG8gV29ybGQ=');
// "Hello World"

// URL 安全编码
const urlEncoded = utils.base64.encodeURI('Hello World');
```

### 加密工具 (utils.crypto)

```typescript
// MD5 哈希
const hash = utils.crypto.md5('password');

// SHA256 哈希
const sha256 = utils.crypto.sha256('password');

// AES 加密
const encrypted = utils.crypto.aes.encrypt('secret data', 'key');

// AES 解密
const decrypted = utils.crypto.aes.decrypt(encrypted, 'key');
```

### URL 工具 (utils.url)

```typescript
// 解析查询字符串
const params = utils.url.parse('name=张三&age=25');
// { name: '张三', age: '25' }

// 序列化查询字符串
const queryString = utils.url.stringify({ name: '张三', age: 25 });
// "name=张三&age=25"

// 获取 URL 参数
const id = utils.url.getParam('id');

// 设置 URL 参数
utils.url.setParam('page', '2');
```

---

## 国际化 API

```typescript
import { t, useI18n } from 'spark';
```

### 在 Script 中使用

```typescript
// 简单翻译
const message = t('common.save');

// 带参数的翻译
const greeting = t('user.greeting', { name: '张三' });

// 复数形式
const items = t('cart.items', { count: 3 });
```

### 在组件中使用

```vue
<template>
  <!-- 使用 $t -->
  <div>{{ $t('common.save') }}</div>
  <div>{{ $t('user.greeting', { name: userName }) }}</div>

  <!-- 在属性中使用 -->
  <w-input :placeholder="$t('user.inputPlaceholder')" />
  <w-button>{{ $t('common.submit') }}</w-button>
</template>

<script setup lang="ts">
import { t, useI18n } from 'spark';

const { locale, t: translate } = useI18n();

// 切换语言
const switchLanguage = (lang: string) => {
  locale.value = lang;
};

// 在 JS 中使用
const title = translate('page.title');
</script>
```

### 多语言文件结构

```
src/
├── locales/
│   ├── zh_CN/
│   │   ├── common.json
│   │   ├── user.json
│   │   └── ...
│   └── en_US/
│       ├── common.json
│       ├── user.json
│       └── ...
```

```json
// locales/zh_CN/common.json
{
  "save": "保存",
  "cancel": "取消",
  "confirm": "确认",
  "delete": "删除",
  "edit": "编辑",
  "add": "新增",
  "search": "搜索",
  "reset": "重置",
  "submit": "提交",
  "success": "操作成功",
  "failed": "操作失败"
}
```

---

## 微前端 API

```typescript
import { micro } from 'spark';
```

### 子应用通信

```typescript
// 发送消息给主应用
micro.emit('event-name', { data: 'value' });

// 监听主应用消息
micro.on('event-name', (data) => {
  console.log('收到消息:', data);
});

// 取消监听
const handler = (data) => console.log(data);
micro.on('event-name', handler);
micro.off('event-name', handler);

// 一次性监听
micro.once('event-name', (data) => {
  console.log('只触发一次:', data);
});
```

### 获取主应用数据

```typescript
// 获取主应用传递的 props
const props = micro.getProps();
console.log(props.token);
console.log(props.userInfo);

// 获取主应用路由信息
const routerInfo = micro.getRouter();
```

---

## 事件总线 API

```typescript
import { useEventBus } from 'spark';
```

### 创建事件总线

```typescript
// 创建事件总线
const bus = useEventBus();

// 定义事件类型
type Events = {
  'user:login': User;
  'user:logout': void;
  'notification:show': { message: string; type: 'success' | 'error' };
};

// 监听事件
const unsubscribe = bus.on('user:login', (user) => {
  console.log('用户登录:', user);
});

// 触发事件
bus.emit('user:login', { id: 1, name: '张三' });

// 取消监听
unsubscribe();
// 或者
bus.off('user:login');
```

### 在组件间通信

```typescript
// 组件 A - 发送事件
import { useEventBus } from 'spark';

const bus = useEventBus();

const handleSave = () => {
  // 保存数据后通知其他组件
  bus.emit('data:updated', { id: 1 });
};

// 组件 B - 监听事件
import { useEventBus } from 'spark';
import { onUnmounted } from 'spark';

const bus = useEventBus();

const unsubscribe = bus.on('data:updated', ({ id }) => {
  console.log('数据已更新:', id);
  refreshData();
});

// 组件卸载时取消监听
onUnmounted(() => {
  unsubscribe();
});
```

---

## 完整使用示例

```vue
<template>
  <div class="user-list">
    <w-button type="primary" @click="handleAdd">
      {{ $t('common.add') }}
    </w-button>

    <w-table :data="userList" :loading="loading">
      <w-table-column prop="name" :label="$t('user.name')" />
      <w-table-column prop="email" :label="$t('user.email')" />
      <w-table-column :label="$t('common.action')">
        <template #default="{ row }">
          <w-button size="small" @click="handleEdit(row)">
            {{ $t('common.edit') }}
          </w-button>
        </template>
      </w-table-column>
    </w-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'spark';
import { t } from 'spark';
import { useEventBus } from 'spark';
import { userApi } from './apis/user';
import type { User } from './types/user';

// 响应式状态
const loading = ref(false);
const userList = ref<User[]>([]);

// 事件总线
const bus = useEventBus();

// 获取数据
const fetchList = async () => {
  loading.value = true;
  try {
    const res = await userApi.getList();
    userList.value = res.data;
  } catch (error) {
    console.error(t('common.failed'));
  } finally {
    loading.value = false;
  }
};

// 新增
const handleAdd = () => {
  bus.emit('navigate', { view: 'userForm', mode: 'add' });
};

// 编辑
const handleEdit = (user: User) => {
  bus.emit('navigate', { view: 'userForm', mode: 'edit', id: user.id });
};

// 监听数据更新
const unsubscribe = bus.on('user:updated', () => {
  fetchList();
});

// 生命周期
onMounted(() => {
  fetchList();
});

onUnmounted(() => {
  unsubscribe();
});
</script>

<style scoped>
.user-list {
  padding: 16px;
}
</style>
```
