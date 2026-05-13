# Role-Aware Business Agent

一个面向业务系统接入的 Python Agent 依赖包。

本项目希望在完全基于 DeepAgents、LangChain、LangGraph 的前提下，提供一个更适合业务系统落地的 Agent 基础能力：让 Agent 在执行任务时具备明确的业务角色，让工具和业务系统能够基于角色做权限判断，并将任务执行过程中的状态信息返回给业务请求方。

## 项目目标

业务系统在接入 Agent 时，通常不只关心“Agent 能不能调用工具”，还需要关心：

- 当前请求是以什么角色发起的；
- 不同角色能看到和使用哪些工具；
- Agent 调用业务系统时，业务系统如何识别本次请求的角色；
- 一个任务当前执行到哪里、状态如何、是否失败、是否可追踪。

本项目的目标是将这些通用能力沉淀为一个 Python 依赖包，业务系统只需要引入该依赖包，即可快速创建具备角色感知、权限边界和任务追踪能力的业务友好型 Agent。

## 核心能力

### 1. 请求 Agent 时携带角色

业务系统在发起 Agent 请求时，可以传入当前用户或当前业务流程对应的角色信息。

Agent 会基于该角色决定：

- 哪些工具对当前请求可见；
- 哪些工具允许被调用；
- 当前任务执行时应该使用什么业务上下文；
- 后续调用业务系统时应该携带什么角色凭证或角色声明。

### 2. 基于角色控制工具可见性

工具注册时可以声明允许访问的角色范围。Agent 在运行前会根据当前请求角色过滤工具集合，避免模型看到或选择无权使用的工具。

这意味着权限约束会尽量前置到 Agent 编排层，而不是等到工具真正执行时才失败。

### 3. Agent 调用工具或业务系统时携带角色

当 Agent 调用工具、HTTP API、RPC 服务或其他业务系统时，会将当前角色上下文一起传递给下游。

业务系统可以继续基于该角色做自己的权限判断，例如：

- 判断当前角色是否可以查询某类数据；
- 判断当前角色是否可以执行写操作；
- 判断当前角色是否可以访问某个租户、组织或业务域；
- 记录业务审计日志。

### 4. 返回任务信息与任务状态

每次 Agent 执行都会生成任务信息和任务状态，并通过异步响应结果和完成事件回调返回给业务请求方。

Agent 项目本身不负责持久化这些任务数据。业务系统可以根据自身的数据模型、审计要求和展示需求，将任务信息存储到自己的数据库、日志系统或任务中心。

任务信息通常包括：

- 任务 ID；
- 请求角色；
- 输入内容；
- 当前状态；
- 开始时间与结束时间；
- 工具调用记录；
- 错误信息；
- 最终输出。

任务状态可以用于业务系统展示执行进度、排查问题或做审计追踪。

## 技术基础

本项目基于以下技术构建：

- DeepAgents：用于构建更复杂的 Agent 执行能力；
- LangChain：用于工具、模型、消息、回调等基础抽象；
- LangGraph：用于定义可观测、可扩展、可恢复的 Agent 执行图；
- Python Package：以依赖包形式提供给业务系统集成。

## 适用场景

- 企业内部智能助手；
- 运营、客服、销售、财务等角色化 Agent；
- 需要严格控制工具权限的业务 Agent；
- 需要对 Agent 执行过程做审计和追踪的系统；
- 多租户、多角色、多业务线共用同一套 Agent 能力的系统。

## 业务系统集成指南

若要将本依赖接入真实业务系统（环境安装、角色与权限建模、工具开发约定、Web 服务中的异步调用、任务结果落库、自定义运行时与测试），请参阅 **[业务系统集成指南](docs/业务系统集成指南.md)**。该文档可直接交给对方开发工程师或 AI 阅读使用。

## 安装方式

### 从 GitHub 安装

需要本机已安装 [Git](https://git-scm.com/)，Python 版本不低于 `3.10`（见 `pyproject.toml`）。

```bash
pip install "git+https://github.com/AICodeFactory/base-agents.git"
```

默认使用仓库的默认分支（一般为 `main`）。如需固定分支或版本标签：

```bash
pip install "git+https://github.com/AICodeFactory/base-agents.git@main"
pip install "git+https://github.com/AICodeFactory/base-agents.git@v1.0.0"
```

安装后仍使用 `from business_agent import ...` 导入（PyPI 分发名为 `role-aware-business-agent`，与导入包名 `business_agent` 不同属正常情况）。

### 本地开发（可编辑安装）

在克隆后的仓库根目录执行：

```bash
pip install -e .
```

可选安装开发依赖：

```bash
pip install -e ".[dev]"
```

## 快速开始

下面示例展示业务系统如何创建一个带角色上下文的 Agent 请求。

```python
import asyncio

from business_agent import AgentRequest, BusinessAgent, RoleContext, TaskEvent, ToolRegistry


async def save_task_event_to_business_system(event: TaskEvent) -> None:
    # 业务系统可以在这里写数据库、消息队列、日志平台或任务中心
    print(event.to_dict())


async def main() -> None:
    tool_registry = ToolRegistry()

    agent = BusinessAgent(
        model="gpt-4.1",
        tool_registry=tool_registry,
        on_complete=save_task_event_to_business_system,
    )

    request = AgentRequest(
        input="帮我查询这个客户最近 30 天的订单情况，并总结异常点",
        role=RoleContext(
            role="sales_manager",
            user_id="u_123",
            tenant_id="tenant_001",
            permissions=["order:read", "customer:read"],
        ),
    )

    result = await agent.ainvoke(request)

    print(result.task_id)
    print(result.status)
    print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
```

## 工具注册示例

工具可以声明自己允许哪些角色访问。

```python
from business_agent import RoleContext, business_tool


@business_tool(
    name="query_orders",
    description="查询客户订单信息",
    allowed_roles=["sales_manager", "customer_service"],
)
async def query_orders(customer_id: str, role_context: RoleContext) -> dict:
    # role_context 会随工具调用传入，业务系统可以继续做权限校验
    return {
        "customer_id": customer_id,
        "tenant_id": role_context.tenant_id,
        "orders": [],
    }
```

当请求角色不是 `sales_manager` 或 `customer_service` 时，该工具不会暴露给 Agent。

## 角色上下文

角色上下文用于描述本次 Agent 请求的业务身份。

建议至少包含：

```python
{
    "role": "sales_manager",
    "user_id": "u_123",
    "tenant_id": "tenant_001",
    "permissions": ["order:read", "customer:read"]
}
```

其中：

- `role` 表示当前业务角色；
- `user_id` 表示发起请求的用户；
- `tenant_id` 表示租户或组织；
- `permissions` 表示更细粒度的权限集合。

业务系统可以根据自身情况扩展字段，例如部门、区域、数据范围、审批级别等。

## 权限模型

本项目建议采用两层权限控制：

### Agent 层权限

Agent 在运行前基于角色过滤工具，控制模型可见的工具范围。

这层权限主要解决“模型能不能看到和选择这个工具”的问题。

### 业务系统层权限

工具或业务系统在真正执行请求时，再基于角色上下文做最终权限判断。

这层权限主要解决“这个请求在业务上是否真的允许执行”的问题。

两层权限配合可以降低越权调用风险，同时保留业务系统自己的权限判断能力。

## 任务状态

Agent 执行任务时会产生状态变化，并将最终状态信息返回给业务请求方。

本依赖包只负责生成标准化的任务状态数据，不内置任务存储。业务系统拿到任务 ID、状态、步骤、错误和输出后，可以自行写入数据库、消息队列、日志平台或任务管理系统。当前实现会在任务进入终态后触发 `on_complete` 回调。

推荐的任务状态包括：

- `created`：任务已创建；
- `running`：任务执行中；
- `waiting_tool`：等待工具调用结果；
- `succeeded`：任务执行成功；
- `failed`：任务执行失败；
- `cancelled`：任务已取消。

业务系统可以保存 Agent 返回的任务结果：

```python
result = await agent.ainvoke(request)

business_task_repository.save(
    task_id=result.task_id,
    status=result.status,
    steps=result.steps,
    error=result.error,
    output=result.output,
)
```

## 架构概览

```text
Business System
      |
      | AgentRequest(input, role_context)
      v
BusinessAgent
      |
      |-- Role-based Tool Filter
      |
      |-- LangGraph / DeepAgents Runtime
      |
      v
Business Tools / APIs
      |
      | request with role_context
      v
Business Permission Check

BusinessAgent
      |
      | TaskResult / TaskEvent
      v
Business System
      |
      | persist by business side
      v
Business System Storage
```

## 业务系统接入方式

业务系统通常只需要完成以下步骤：

1. 安装本依赖包；
2. 定义业务角色和权限字段；
3. 注册业务工具，并声明工具可见角色；
4. 初始化 `BusinessAgent`；
5. 发起请求时传入 `RoleContext`；
6. 接收 Agent 返回的任务信息和状态；
7. 业务系统自行存储任务数据，并按需提供查询能力。

## 设计原则

- 角色上下文必须显式传入，不依赖隐式全局变量；
- Agent 层只做工具可见性控制，不替代业务系统最终鉴权；
- 工具调用必须携带角色上下文，方便业务系统审计和鉴权；
- 任务执行过程必须可追踪，但任务数据由业务系统自行持久化；
- 依赖包只提供通用 Agent 能力，不绑定具体业务系统。

## 后续规划

- 支持运行中任务状态事件流，方便业务系统实时接收并存储任务进度；
- 支持任务取消接口；
- 支持工具调用审计日志；
- 支持基于权限表达式的工具可见性控制；
- 支持多租户隔离；
- 支持 LangGraph checkpoint 与任务状态联动；
- 支持 FastAPI / Django 等业务框架集成示例。

## License

TBD
