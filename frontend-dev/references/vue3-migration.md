# Vue2 到 Vue3 迁移详细规则

> 本文档详细说明 Vue2 组件迁移到 Vue3 Composition API 的规则和最佳实践。

## 目录

- [核心原则](#核心原则)
- [迁移映射表](#迁移映射表)
- [迁移步骤](#迁移步骤)
- [常见场景迁移](#常见场景迁移)
- [注意事项](#注意事项)
- [审计报告模板](#审计报告模板)

---

## 核心原则

### 1. 行为等价原则（最高优先级）

**任何迁移都必须保证组件逻辑与行为与原实现保持完全等价。**

**要求**：
- 输入相同 → 输出相同
- 副作用行为相同（DOM 操作、事件触发、API 调用等）
- 错误处理行为相同
- 边界情况处理相同

**无法确保等价时**：
- 必须立即中止操作
- 明确标注风险点
- 标记为需要人工处理

### 2. 最小改动原则

**除非明确授权，禁止修改以下内容**：

**禁止修改**：
- 组件模板结构（除非是 Vue3 语法要求）
- 样式代码（CSS/SCSS）
- 公共接口（props、emits 的定义）
- 文件结构和文件位置

**允许修改**：
- 模板中的 Vue3 语法转换（`v-model`、事件绑定等）
- Script 部分的完整迁移

### 3. 全量迁移原则

**允许修改组件内所有部分以达到纯 Vue3 Composition API 写法**：

**允许修改**：
- `data()` → `ref()` 或 `reactive()`
- `props` → `defineProps<T>()`
- `methods` → 普通顶层函数
- `computed` → `computed()`
- `watch` → `watch()` 或 `watchEffect()`
- 生命周期钩子 → Composition API 钩子
- 组件整体结构 → `<script setup lang="ts">`

**必须保持**：
- 组件名称
- 事件接口（emits）
- 文件路径
- 公共 API（props、emits 签名）

### 4. 代码质量要求

**转换后必须满足**：
- 不能有任何 lint 错误
- 完整类型声明（禁止 `any`）
- Props、emits、函数返回值必须显式声明类型
- 禁止引入非官方依赖

---

## 迁移映射表

### Options API → Composition API

| Vue2 Options API | Vue3 Composition API | 说明 |
|------------------|---------------------|------|
| `data()` | `ref()` / `reactive()` | 响应式数据 |
| `props` | `defineProps<T>()` | 组件属性 |
| `emits` | `defineEmits<{}>()` | 组件事件 |
| `computed` | `computed()` | 计算属性 |
| `watch` | `watch()` / `watchEffect()` | 侦听器 |
| `methods` | 普通顶层函数 | 方法 |
| `beforeCreate` | `setup()` | 创建前 |
| `created` | `setup()` | 创建后 |
| `beforeMount` | `onBeforeMount()` | 挂载前 |
| `mounted` | `onMounted()` | 挂载后 |
| `beforeUpdate` | `onBeforeUpdate()` | 更新前 |
| `updated` | `onUpdated()` | 更新后 |
| `beforeDestroy` | `onBeforeUnmount()` | 卸载前 |
| `destroyed` | `onUnmounted()` | 卸载后 |
| `errorCaptured` | `onErrorCaptured()` | 错误捕获 |

### 模板语法变化

| Vue2 | Vue3 | 说明 |
|------|------|------|
| `v-model` | `v-model` 或 `v-model:propName` | 双向绑定 |
| `v-on:hook:mounted` | `@vue:mounted` | 生命周期事件 |
| `slot` | `v-slot` 或 `#` | 插槽 |
| `$listeners` | 合并到 `$attrs` | 事件监听 |
| `$scopedSlots` | `$slots` | 作用域插槽 |

### 样式深度选择器

| Vue2 | Vue3 |
|------|------|
| `/deep/` | `:deep()` |
| `>>>` | `:deep()` |
| `::v-deep` | `:deep()` |

---

## 迁移步骤

### Step 1: 分析原组件

1. 读取原 Vue2 组件代码
2. 识别所有需要迁移的部分：
   - data
   - props
   - computed
   - watch
   - methods
   - 生命周期钩子
   - 副作用（事件监听、定时器等）
3. 记录组件的公共接口

### Step 2: 创建类型定义

```typescript
// Props 类型
interface Props {
  title: string;
  userId?: number;
  visible: boolean;
}

// Emits 类型
interface Emits {
  (e: 'update:visible', value: boolean): void;
  (e: 'submit', data: FormData): void;
  (e: 'cancel'): void;
}

// 数据类型
interface FormData {
  name: string;
  email: string;
}
```

### Step 3: 迁移 Script 部分

```vue
<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'spark';

// 1. Props 定义
interface Props {
  title: string;
  userId?: number;
  visible: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  userId: 0,
  visible: false
});

// 2. Emits 定义
const emits = defineEmits<{
  'update:visible': [value: boolean];
  'submit': [data: FormData];
  'cancel': [];
}>();

// 3. 响应式状态（原 data）
const loading = ref(false);
const formData = reactive<FormData>({
  name: '',
  email: ''
});

// 4. 计算属性（原 computed）
const displayName = computed(() => {
  return formData.name || '未命名';
});

// 5. 方法（原 methods）
const handleSubmit = () => {
  emits('submit', { ...formData });
};

const handleCancel = () => {
  emits('cancel');
  emits('update:visible', false);
};

// 6. 侦听器（原 watch）
watch(() => props.visible, (newVal) => {
  if (newVal) {
    fetchData();
  }
});

// 7. 生命周期（原 mounted/beforeDestroy 等）
onMounted(() => {
  fetchData();
});

onUnmounted(() => {
  // 清理副作用
});
</script>
```

### Step 4: 迁移模板语法

```vue
<template>
  <!-- v-model 变化 -->
  <!-- Vue2: <CustomInput v-model="value" /> -->
  <!-- Vue3: 保持不变，或使用 v-model:value -->
  <CustomInput v-model="value" />

  <!-- 插槽语法变化 -->
  <!-- Vue2: <template #default="slotProps"> -->
  <!-- Vue3: 推荐使用 # -->
  <template #default="slotProps">
    {{ slotProps.data }}
  </template>

  <!-- 响应式访问变化 -->
  <!-- Vue2: {{ this.userName }} -->
  <!-- Vue3: {{ userName }} (移除 this) -->
  <div>{{ userName }}</div>
</template>
```

### Step 5: 迁移样式

```vue
<style scoped>
/* Vue2 深度选择器 */
/* /deep/ .el-input { } */

/* Vue3 深度选择器 */
:deep(.w-input) {
  width: 100%;
}

/* Vue2 全局样式 */
/* >>> .global-class { } */

/* Vue3 全局样式 */
:global(.global-class) {
  color: red;
}
</style>
```

### Step 6: 验证和测试

1. 运行 TypeScript 类型检查
2. 运行 ESLint 检查
3. 运行单元测试
4. 手动测试组件功能

---

## 常见场景迁移

### 场景 1: 基础表单组件

**Vue2 原代码**：
```vue
<template>
  <div class="user-form">
    <el-form ref="form" :model="form" :rules="rules">
      <el-form-item label="姓名" prop="name">
        <el-input v-model="form.name" />
      </el-form-item>
      <el-form-item label="邮箱" prop="email">
        <el-input v-model="form.email" />
      </el-form-item>
    </el-form>
  </div>
</template>

<script>
export default {
  name: 'UserForm',
  props: {
    visible: Boolean,
    userData: Object
  },
  data() {
    return {
      form: {
        name: '',
        email: ''
      },
      rules: {
        name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
        email: [{ required: true, message: '请输入邮箱', trigger: 'blur' }]
      }
    };
  },
  computed: {
    isEdit() {
      return !!this.userData;
    }
  },
  watch: {
    userData: {
      handler(val) {
        if (val) {
          this.form = { ...val };
        }
      },
      immediate: true
    }
  },
  methods: {
    submit() {
      this.$refs.form.validate(valid => {
        if (valid) {
          this.$emit('submit', this.form);
        }
      });
    },
    reset() {
      this.$refs.form.resetFields();
    }
  }
};
</script>
```

**Vue3 迁移后**：
```vue
<template>
  <div class="user-form">
    <w-form ref="formRef" :model="form" :rules="rules">
      <w-form-item label="姓名" prop="name">
        <w-input v-model="form.name" />
      </w-form-item>
      <w-form-item label="邮箱" prop="email">
        <w-input v-model="form.email" />
      </w-form-item>
    </w-form>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'spark';
import type { FormInstance, FormRules } from 'spark';

// Props 定义
interface Props {
  visible: boolean;
  userData?: User | null;
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  userData: null
});

// Emits 定义
const emits = defineEmits<{
  submit: [data: User];
}>();

// 响应式状态
const formRef = ref<FormInstance>();
const form = reactive<User>({
  name: '',
  email: ''
});

const rules = reactive<FormRules>({
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  email: [{ required: true, message: '请输入邮箱', trigger: 'blur' }]
});

// 计算属性
const isEdit = computed(() => !!props.userData);

// 侦听器
watch(() => props.userData, (val) => {
  if (val) {
    Object.assign(form, val);
  }
}, { immediate: true });

// 方法
const submit = async () => {
  const valid = await formRef.value?.validate();
  if (valid) {
    emits('submit', { ...form });
  }
};

const reset = () => {
  formRef.value?.resetFields();
};

// 暴露方法给父组件
defineExpose({
  submit,
  reset
});
</script>
```

### 场景 2: 带副作用的组件

**Vue2 原代码**：
```vue
<script>
export default {
  data() {
    return {
      scrollY: 0,
      timer: null
    };
  },
  mounted() {
    window.addEventListener('scroll', this.handleScroll);
    this.timer = setInterval(this.pollData, 5000);
  },
  beforeDestroy() {
    window.removeEventListener('scroll', this.handleScroll);
    if (this.timer) {
      clearInterval(this.timer);
    }
  },
  methods: {
    handleScroll() {
      this.scrollY = window.scrollY;
    },
    pollData() {
      // 轮询数据
    }
  }
};
</script>
```

**Vue3 迁移后**：
```vue
<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'spark';

// 响应式状态
const scrollY = ref(0);
let timer: ReturnType<typeof setInterval> | null = null;

// 方法
const handleScroll = () => {
  scrollY.value = window.scrollY;
};

const pollData = () => {
  // 轮询数据
};

// 副作用管理
onMounted(() => {
  window.addEventListener('scroll', handleScroll);
  timer = setInterval(pollData, 5000);
});

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll);
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
});
</script>
```

### 场景 3: 复杂状态管理

**Vue2 原代码**：
```vue
<script>
import { mapState, mapActions } from 'vuex';

export default {
  computed: {
    ...mapState('user', ['userInfo', 'token']),
    isLoggedIn() {
      return !!this.token;
    }
  },
  methods: {
    ...mapActions('user', ['login', 'logout']),
    async handleLogin() {
      await this.login(this.form);
    }
  }
};
</script>
```

**Vue3 迁移后**：
```vue
<script setup lang="ts">
import { computed } from 'spark';
import { storeToRefs } from 'spark';
import { useUserStore } from '@/stores/user';

const userStore = useUserStore();

// 解构响应式状态
const { userInfo, token } = storeToRefs(userStore);

// 计算属性
const isLoggedIn = computed(() => !!token.value);

// 方法
const handleLogin = async () => {
  await userStore.login(form);
};
</script>
```

### 场景 4: 命名冲突处理

**Vue2 原代码**：
```javascript
data() {
  return {
    hintStatus: ''
  };
},
methods: {
  async fetchData() {
    const res = await api.getData();
    const { hintStatus, portalSchemeCode } = res.data || {};
    this.hintStatus = hintStatus;
  }
}
```

**Vue3 迁移后（正确处理命名冲突）**：
```typescript
// 响应式变量
const hintStatus = ref('');
const portalSchemeCode = ref('');

// 方法 - 使用重命名避免冲突
const fetchData = async () => {
  const res = await api.getData();
  // ✅ 正确：解构时重命名
  const {
    hintStatus: hintStatusData,
    portalSchemeCode: portalSchemeCodeData
  } = res.data || {};

  // 正确赋值
  hintStatus.value = hintStatusData;
  portalSchemeCode.value = portalSchemeCodeData;
};
```

---

## 注意事项

### 1. 响应式丢失问题

```typescript
// ❌ 错误：解构会丢失响应式
const { name, age } = props;

// ✅ 正确：使用 toRefs
import { toRefs } from 'spark';
const { name, age } = toRefs(props);

// ✅ 正确：直接使用 props
console.log(props.name);
```

### 2. this 指向变化

```typescript
// Vue2
this.$refs.form.validate();
this.$emit('change', value);
this.$router.push('/path');

// Vue3
formRef.value?.validate();
emits('change', value);
// router.push('/path'); // 无路由模式下谨慎使用
```

### 3. 生命周期时机

```typescript
// Vue2 created 在 setup 中执行
// setup() 相当于 beforeCreate 和 created

// Vue2
created() {
  this.fetchData();
}

// Vue3 - 直接在 setup 顶层执行
const fetchData = async () => { /* ... */ };
fetchData(); // 相当于 created
```

### 4. 组件引用

```vue
<script setup lang="ts">
import { ref } from 'spark';
import ChildComponent from './ChildComponent.vue';

const childRef = ref<InstanceType<typeof ChildComponent>>();

const callChildMethod = () => {
  childRef.value?.someMethod();
};
</script>

<template>
  <ChildComponent ref="childRef" />
</template>
```

### 5. Props 默认值

```typescript
// Vue2
props: {
  title: {
    type: String,
    default: '默认标题'
  },
  count: {
    type: Number,
    default: 0
  },
  items: {
    type: Array,
    default: () => []
  }
}

// Vue3
interface Props {
  title?: string;
  count?: number;
  items?: Item[];
}

const props = withDefaults(defineProps<Props>(), {
  title: '默认标题',
  count: 0,
  items: () => []
});
```

---

## 审计报告模板

每次迁移必须输出完整的审计报告：

```markdown
## 🔍 Refactor Audit Block

### 基本信息
- **迁移文件路径**: src/views/User/List.vue
- **迁移阶段**: Vue2 to Vue3 Composition API Migration
- **执行时间**: 2025-12-17 15:30:00
- **迁移类型**: 整体 Composition API 迁移

### 行为等价性验证
- **行为是否等价**: ✅ Yes
- **等价性说明**:
  - ✅ 组件渲染逻辑完全一致
  - ✅ 用户交互行为完全一致
  - ✅ 数据响应式更新完全一致
  - ✅ 事件触发时机完全一致

### 副作用管理
- **副作用变更**: 无新增，清理函数迁移完备
- **副作用详细列表**:
  1. DOM 事件监听: window scroll 事件（已迁移清理函数到 onUnmounted）
  2. 定时器: setInterval，每 5 秒更新数据（已迁移清理函数）

### 命名冲突处理
- **是否发现命名冲突**: ✅ Yes
- **冲突处理**:
  - 发现 `hintStatus` 变量冲突，已重命名为 `hintStatusData`

### 代码质量检查
- **Lint 检查**: ✅ 通过（0 errors, 0 warnings）
- **TypeScript 类型**: ✅ 完整（无 any，所有类型显式声明）

### 回滚能力
- **是否可回滚**: ✅ Yes
- **回滚方式**: `git revert <commit-hash>`

### 风险评估
- **风险等级**: 🟢 低
- **潜在风险**: 无重大风险

### 测试建议
- 建议测试场景:
  1. 用户列表加载和显示
  2. 筛选和排序功能
  3. 分页功能

### 人工审核要点
1. 验证副作用清理函数是否正确
2. 验证命名冲突处理是否合理
3. 验证代码质量是否符合规范
```

---

## 迁移检查清单

### 迁移前
- [ ] 分析原组件结构
- [ ] 识别所有副作用
- [ ] 记录公共接口
- [ ] 确认迁移范围

### 迁移中
- [ ] 创建类型定义
- [ ] 迁移 Props/Emits
- [ ] 迁移响应式状态
- [ ] 迁移计算属性
- [ ] 迁移侦听器
- [ ] 迁移方法
- [ ] 迁移生命周期
- [ ] 处理副作用清理
- [ ] 检查命名冲突
- [ ] 更新模板语法
- [ ] 更新样式语法

### 迁移后
- [ ] TypeScript 类型检查通过
- [ ] ESLint 检查通过
- [ ] 单元测试通过
- [ ] 手动功能测试
- [ ] 输出审计报告
- [ ] 确认可回滚
