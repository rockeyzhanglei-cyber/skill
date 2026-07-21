# 控制类API参考

## PangoAppUtil（应用工具类）

### 数据模型获取

```typescript
import {PangoAppUtil} from "pango-framework-vue";

// 获取数据集
const dataset = PangoAppUtil.getDataset('userDataset', yView);

// 获取数据列表
const dataList = PangoAppUtil.getDataList('statusList', yView);
```

### 组件获取

```typescript
// 获取组件实例
let yButton = PangoAppUtil.getComponent('submitButton', yView) as YButton;
```

### 对象与数据集转换

```typescript
// 对象转数据集
const user = { id: 1, name: '张三' };
PangoAppUtil.Object2Dataset(user, dataset);

// 数据集转对象
const userObj = PangoAppUtil.Dataset2Object(dataset);

// 数组转数据集
const users = [{ id: 1, name: '张三' }];
PangoAppUtil.Array2Dataset(users, dataset);

// 数据集转数组
const userArray = PangoAppUtil.Dataset2Array(dataset);
```

## Request（HTTP请求）

```typescript
import request from '@/utils/request';

// GET请求
request.get('/api/user/list', { page: 1, size: 10 })
    .then(res => {
        console.log(res);
    });

// POST请求
request.post('/api/user/add', { name: 'test', age: 20 })
    .then(res => {
        console.log(res);
    });

// DELETE请求
request.del('/api/user/delete/1', { id: 1 });
```

## WindowAPI（窗口管理）

```typescript
import {WindowAPI} from "pango-framework-vue";

// 显示成功消息
WindowAPI.showSuccessShortMessage('操作成功');

// 显示错误消息
WindowAPI.showErrorShortMessage('操作失败');

// 显示确认对话框
WindowAPI.showConfirmDialog(
    '确定要删除吗？',
    () => { deleteRecord(); },
    () => { console.log('取消'); }
);

// 弹出页面
WindowAPI.popPage('userDetailPage', null, new Map([['userId', 123]]));

// 弹出视图
WindowAPI.popView('userEditView', null, { title: '编辑用户', width: 800 });

// 弹出抽屉
WindowAPI.popViewDrawer('userEditView', null, { title: '编辑', placement: 'right', width: 500 });

// 关闭窗口
WindowAPI.closeWindow(key);

// 显示加载状态
WindowAPI.showRequestLoading();
fetchData().then(() => {
    WindowAPI.closeRequestLoading();
});
```

## 快速参考

| 操作 | API方法 | 说明 |
|------|---------|------|
| 获取数据集 | PangoAppUtil.getDataset() | 获取Dataset实例 |
| 获取组件 | PangoAppUtil.getComponent() | 获取组件实例 |
| 对象转数据集 | PangoAppUtil.Object2Dataset() | 将对象转换为数据集 |
| 数据集转对象 | PangoAppUtil.Dataset2Object() | 将数据集转换为对象 |
| 发送GET请求 | request.get() | HTTP GET请求 |
| 发送POST请求 | request.post() | HTTP POST请求 |
| 弹出页面 | WindowAPI.popPage() | 弹出模态对话框 |
| 弹出视图 | WindowAPI.popView() | 弹出视图对话框 |
| 显示消息 | WindowAPI.showSuccessShortMessage() | 显示成功消息 |
| 显示确认框 | WindowAPI.showConfirmDialog() | 显示确认对话框 |
| 显示加载 | WindowAPI.showRequestLoading() | 显示加载状态 |
