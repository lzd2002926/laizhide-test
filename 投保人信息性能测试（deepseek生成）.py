import time
import threading
import concurrent.futures
import requests
import psutil
import json
import random
import statistics
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

# ========== 测试数据生成器 ==========
class InsurantDataGenerator:
    """生成性能测试用的投保人数据"""
    
    SURNAMES = ['王', '李', '张', '刘', '陈', '杨', '赵', '黄', '周', '吴']
    GIVEN_NAMES = ['伟', '芳', '娜', '敏', '静', '涛', '军', '强', '鹏', '宇']
    
    @staticmethod
    def generate_id() -> str:
        """生成虚拟身份证号"""
        area = '110101'
        year = random.randint(1960, 2000)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        birth = f"{year}{month:02d}{day:02d}"
        seq = f"{random.randint(0, 999):03d}"
        check = str(random.randint(0, 9))
        return area + birth + seq + check
    
    @staticmethod
    def generate_phone() -> str:
        """生成手机号"""
        prefixes = ['130', '131', '132', '155', '156', '185', '186', '188', '189']
        return random.choice(prefixes) + f"{random.randint(10000000, 99999999)}"
    
    @classmethod
    def generate_one(cls) -> Dict:
        """生成单条投保人数据"""
        surname = random.choice(cls.SURNAMES)
        given_name = ''.join(random.choices(cls.GIVEN_NAMES, k=random.randint(1, 2)))
        return {
            'name': surname + given_name,
            'id_card': cls.generate_id(),
            'phone': cls.generate_phone(),
            'email': f"test_{random.randint(1, 10000)}@example.com",
            'amount': random.randint(1000, 100000),
            'policy_type': random.choice(['health', 'life', 'accident', 'property'])
        }

# ========== 性能测试框架 ==========
@dataclass
class TestResult:
    """单次测试结果"""
    success: bool
    response_time: float  # 毫秒
    error_msg: str = ""
    status_code: int = 0

@dataclass
class PerformanceReport:
    """性能测试报告"""
    total_requests: int = 0
    success_count: int = 0
    fail_count: int = 0
    response_times: List[float] = field(default_factory=list)
    errors: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    start_time: float = 0
    end_time: float = 0
    
    @property
    def qps(self) -> float:
        """每秒请求数"""
        duration = self.end_time - self.start_time
        return self.total_requests / duration if duration > 0 else 0
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        return (self.success_count / self.total_requests * 100) if self.total_requests > 0 else 0
    
    def get_percentile(self, p: float) -> float:
        """获取响应时间百分位数（毫秒）"""
        if not self.response_times:
            return 0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * p / 100)
        return sorted_times[min(idx, len(sorted_times) - 1)]
    
    def print_report(self, test_name: str = "性能测试"):
        """打印测试报告"""
        print(f"\n{'='*60}")
        print(f"📊 {test_name} - 性能测试报告")
        print(f"{'='*60}")
        print(f"总请求数:        {self.total_requests}")
        print(f"成功数:          {self.success_count}")
        print(f"失败数:          {self.fail_count}")
        print(f"成功率:          {self.success_rate:.2f}%")
        print(f"QPS:             {self.qps:.2f} req/s")
        print(f"测试时长:        {self.end_time - self.start_time:.2f}秒")
        print(f"\n📈 响应时间分布 (ms):")
        print(f"  最小值:        {min(self.response_times):.2f}" if self.response_times else "  最小值:        N/A")
        print(f"  平均值:        {statistics.mean(self.response_times):.2f}" if self.response_times else "  平均值:        N/A")
        print(f"  P50 (中位数):  {self.get_percentile(50):.2f}")
        print(f"  P90:           {self.get_percentile(90):.2f}")
        print(f"  P95:           {self.get_percentile(95):.2f}")
        print(f"  P99:           {self.get_percentile(99):.2f}")
        print(f"  最大值:        {max(self.response_times):.2f}" if self.response_times else "  最大值:        N/A")
        
        if self.errors:
            print(f"\n❌ 错误统计:")
            for error_type, count in sorted(self.errors.items(), key=lambda x: -x[1]):
                print(f"  {error_type}: {count}次")

class PerformanceTester:
    """HTTP性能测试器"""
    
    def __init__(self, base_url: str, api_key: str = ""):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}' if api_key else ''
        })
    
    def submit_insurant(self, data: Dict) -> TestResult:
        """提交单个投保人数据"""
        start_time = time.time()
        try:
            response = self.session.post(
                f"{self.base_url}/api/insurant/submit",
                json=data,
                timeout=30
            )
            response_time = (time.time() - start_time) * 1000  # 转换为毫秒
            
            if response.status_code in [200, 201]:
                return TestResult(success=True, response_time=response_time, status_code=response.status_code)
            else:
                return TestResult(
                    success=False, 
                    response_time=response_time,
                    status_code=response.status_code,
                    error_msg=f"HTTP {response.status_code}"
                )
        except requests.exceptions.Timeout:
            response_time = (time.time() - start_time) * 1000
            return TestResult(success=False, response_time=response_time, error_msg="Timeout")
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return TestResult(success=False, response_time=response_time, error_msg=str(e))
    
    def run_load_test(self, concurrent: int, total_requests: int, ramp_up: int = 0) -> PerformanceReport:
        """执行负载测试
        
        Args:
            concurrent: 并发线程数
            total_requests: 总请求数
            ramp_up: 爬坡时间（秒），0表示立即全并发
        """
        report = PerformanceReport()
        report.start_time = time.time()
        
        # 预生成所有测试数据
        test_data_list = [InsurantDataGenerator.generate_one() for _ in range(total_requests)]
        
        def worker(worker_id: int, data: Dict) -> Tuple[int, TestResult]:
            """工作线程"""
            result = self.submit_insurant(data)
            return worker_id, result
        
        # 控制爬坡
        if ramp_up > 0:
            delay_per_request = ramp_up / total_requests
        else:
            delay_per_request = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent) as executor:
            futures = []
            for i, data in enumerate(test_data_list):
                if ramp_up > 0 and i > 0:
                    time.sleep(delay_per_request)
                future = executor.submit(worker, i, data)
                futures.append(future)
            
            # 收集结果
            for future in concurrent.futures.as_completed(futures):
                _, result = future.result()
                report.total_requests += 1
                if result.success:
                    report.success_count += 1
                else:
                    report.fail_count += 1
                    report.errors[result.error_msg] += 1
                report.response_times.append(result.response_time)
        
        report.end_time = time.time()
        return report
    
    def monitor_system_resources(self, duration_seconds: int = 60) -> Dict:
        """监控系统资源使用情况（独立进程）"""
        print(f"\n📊 开始监控系统资源，持续{duration_seconds}秒...")
        
        cpu_samples = []
        memory_samples = []
        
        start_time = time.time()
        while time.time() - start_time < duration_seconds:
            cpu_samples.append(psutil.cpu_percent(interval=1))
            memory_samples.append(psutil.virtual_memory().percent)
        
        return {
            'cpu': {
                'avg': statistics.mean(cpu_samples),
                'max': max(cpu_samples),
                'min': min(cpu_samples)
            },
            'memory': {
                'avg': statistics.mean(memory_samples),
                'max': max(memory_samples),
                'min': min(memory_samples)
            }
        }

# ========== 主测试流程 ==========
def run_performance_test_suite(base_url: str, api_key: str = ""):
    """运行完整的性能测试套件"""
    
    tester = PerformanceTester(base_url, api_key)
    
    print("🚀 开始投保人信息性能测试")
    print(f"目标服务器: {base_url}")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 测试场景配置
    test_scenarios = [
        {"name": "⚡ 轻负载测试", "concurrent": 10, "total": 100, "ramp_up": 2},
        {"name": "🔥 中负载测试", "concurrent": 50, "total": 500, "ramp_up": 5},
        {"name": "💪 高负载测试", "concurrent": 100, "total": 1000, "ramp_up": 10},
        {"name": "🚨 压力测试", "concurrent": 200, "total": 2000, "ramp_up": 15},
    ]
    
    all_reports = []
    
    for scenario in test_scenarios:
        print(f"\n{'~'*60}")
        print(f"执行: {scenario['name']}")
        print(f"并发数: {scenario['concurrent']}, 总请求: {scenario['total']}")
        
        # 执行测试
        report = tester.run_load_test(
            concurrent=scenario['concurrent'],
            total_requests=scenario['total'],
            ramp_up=scenario['ramp_up']
        )
        report.print_report(scenario['name'])
        all_reports.append((scenario['name'], report))
        
        # 测试间休息，让系统恢复
        print("\n⏸️  等待5秒后继续下一轮测试...")
        time.sleep(5)
    
    # 输出汇总对比
    print(f"\n{'='*80}")
    print("📈 性能测试汇总对比")
    print(f"{'='*80}")
    print(f"{'测试场景':<20} {'成功率':<12} {'QPS':<12} {'P50(ms)':<12} {'P99(ms)':<12}")
    print(f"{'-'*80}")
    for name, report in all_reports:
        print(f"{name:<20} {report.success_rate:>5.2f}%{'':<6} "
              f"{report.qps:>8.2f}{'':<4} "
              f"{report.get_percentile(50):>8.2f}{'':<4} "
              f"{report.get_percentile(99):>8.2f}")
    
    return all_reports

# ========== 简单健康检查（不依赖外部API） ==========
def mock_performance_test():
    """模拟性能测试（不依赖真实HTTP服务器）"""
    
    print("🏥 模拟性能测试模式 - 仅测试本地代码性能")
    
    class MockTester:
        def submit_insurant(self, data):
            start = time.time()
            time.sleep(random.uniform(0.01, 0.05))  # 模拟网络延迟
            elapsed = (time.time() - start) * 1000
            # 模拟5%的失败率
            success = random.random() > 0.05
            return TestResult(
                success=success,
                response_time=elapsed,
                error_msg="" if success else "Simulated failure"
            )
        
        def run_load_test(self, concurrent, total_requests, ramp_up=0):
            report = PerformanceReport()
            report.start_time = time.time()
            
            test_data = [InsurantDataGenerator.generate_one() for _ in range(total_requests)]
            
            def worker(data):
                return self.submit_insurant(data)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent) as executor:
                futures = [executor.submit(worker, data) for data in test_data]
                
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    report.total_requests += 1
                    if result.success:
                        report.success_count += 1
                    else:
                        report.fail_count += 1
                        report.errors[result.error_msg] += 1
                    report.response_times.append(result.response_time)
            
            report.end_time = time.time()
            return report
    
    mock = MockTester()
    
    # 运行简单测试
    report = mock.run_load_test(concurrent=50, total_requests=500)
    report.print_report("模拟性能测试")
    
    return report

# ========== 主入口 ==========
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='投保人信息性能测试工具')
    parser.add_argument('--url', type=str, help='API服务器地址，例如: http://localhost:8080')
    parser.add_argument('--api-key', type=str, default='', help='API密钥（可选）')
    parser.add_argument('--mock', action='store_true', help='运行模拟测试（不依赖真实服务器）')
    
    args = parser.parse_args()
    
    if args.mock:
        # 模拟测试模式
        mock_performance_test()
    elif args.url:
        # 真实API测试模式
        run_performance_test_suite(args.url, args.api_key)
    else:
        print("❌ 请指定测试模式:")
        print("   真实API测试: python test.py --url http://your-api-server.com")
        print("   模拟测试:    python test.py --mock")
        print("\n示例:")
        print("   python test.py --mock")
        print("   python test.py --url http://localhost:8080")
        print("   python test.py --url https://test-api.example.com --api-key your_key")