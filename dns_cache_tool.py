#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import dns.resolver
import requests
import socket
import json
import time
import re
import threading
import csv
import configparser
import copy
import random
import statistics
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from queue import Queue

class DNSRateLimiter:
    """DNS查询速率限制器，确保每秒不超过指定次数的查询"""
    def __init__(self, queries_per_second=12):
        self.queries_per_second = queries_per_second
        self.query_times = []
        self.lock = threading.Lock()
    
    def wait_if_needed(self):
        """如果需要，等待以满足速率限制"""
        with self.lock:
            current_time = time.time()
            
            # 移除一秒前的查询记录
            self.query_times = [t for t in self.query_times if current_time - t < 1.0]
            
            # 如果当前查询次数已达到限制，则等待
            if len(self.query_times) >= self.queries_per_second:
                sleep_time = 1.0 - (current_time - self.query_times[0])
                if sleep_time > 0:
                    time.sleep(sleep_time)
            
            # 记录当前查询时间
            self.query_times.append(time.time())

class Config:
    """配置管理器"""
    def __init__(self, config_file="config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        # 设置默认配置
        self.default_config = {
            'General': {
                'TargetCount': '2000',
                'DataDirectory': 'data',
            },
            'DNS': {
                'QueriesPerSecond': '12',
                'MaxWorkers': '12',
                'Timeout': '1',
                'BatchSize': '100',
            },
            'Crawler': {
                'ParseJavaScript': 'false',
                'ParseCSS': 'false',
                'ParseImages': 'false',
                'ParseMetaTags': 'false',
                'UserAgent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Timeout': '10',
                'CollectThreads': '5',  # 域名收集线程数
            },
            'Export': {
                'DefaultFormat': 'json',
                'IncludeDNSInfo': 'true',
            }
        }
        
        # 配置项的中文名称和描述
        self.config_names = {
            'General': '常规设置',
            'DNS': 'DNS查询设置',
            'Crawler': '网页爬取设置',
            'Export': '导出设置',
            'TargetCount': '目标域名数量',
            'DataDirectory': '数据存储目录',
            'QueriesPerSecond': '每秒查询次数',
            'MaxWorkers': '最大线程数',
            'Timeout': '超时时间(秒)',
            'BatchSize': '批处理大小',
            'ParseJavaScript': '解析JavaScript文件',
            'ParseCSS': '解析CSS文件',
            'ParseImages': '解析图片链接',
            'ParseMetaTags': '解析Meta标签',
            'UserAgent': '浏览器标识',
            'CollectThreads': '域名收集线程数',
            'DefaultFormat': '默认导出格式',
            'IncludeDNSInfo': '包含DNS查询结果'
        }
        
        # 配置项的详细说明
        self.config_descriptions = {
            'TargetCount': '要收集的域名总数',
            'DataDirectory': '用于存储域名文件的目录',
            'QueriesPerSecond': 'DNS查询速率限制（每秒最多查询次数）',
            'MaxWorkers': 'DNS查询使用的最大线程数',
            'Timeout': 'DNS查询和网页请求的超时时间',
            'BatchSize': '每批处理的域名数量',
            'ParseJavaScript': '是否从JavaScript文件中提取域名（true/false）',
            'ParseCSS': '是否从CSS文件中提取域名（true/false）',
            'ParseImages': '是否从图片链接中提取域名（true/false）',
            'ParseMetaTags': '是否从Meta标签中提取域名（true/false）',
            'UserAgent': '访问网页时使用的浏览器标识',
            'CollectThreads': '域名收集过程使用的线程数',
            'DefaultFormat': '默认的结果导出格式（json/csv）',
            'IncludeDNSInfo': '保存域名文件时是否包含DNS查询结果（true/false）'
        }
        
        self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        # 先设置默认配置
        for section, options in self.default_config.items():
            if not self.config.has_section(section):
                self.config.add_section(section)
            for option, value in options.items():
                self.config.set(section, option, value)
        
        # 尝试从文件加载配置
        if os.path.exists(self.config_file):
            try:
                self.config.read(self.config_file, encoding='utf-8')
                print(f"已加载配置文件: {self.config_file}")
            except Exception as e:
                print(f"加载配置文件出错: {e}")
        else:
            # 保存默认配置
            self.save_config()
            print(f"已创建默认配置文件: {self.config_file}")
    
    def save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            print(f"配置已保存到: {self.config_file}")
        except Exception as e:
            print(f"保存配置文件时出错: {e}")
    
    def get(self, section, option, fallback=None):
        """获取配置值"""
        return self.config.get(section, option, fallback=fallback)
    
    def getint(self, section, option, fallback=None):
        """获取整数配置值"""
        return self.config.getint(section, option, fallback=fallback)
    
    def getfloat(self, section, option, fallback=None):
        """获取浮点数配置值"""
        return self.config.getfloat(section, option, fallback=fallback)
    
    def getboolean(self, section, option, fallback=None):
        """获取布尔配置值"""
        return self.config.getboolean(section, option, fallback=fallback)
    
    def set(self, section, option, value):
        """设置配置值"""
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, option, str(value))
    
    def get_name(self, key):
        """获取配置项的中文名称"""
        return self.config_names.get(key, key)
    
    def get_description(self, key):
        """获取配置项的中文描述"""
        return self.config_descriptions.get(key, "")

class DNSPerformanceTester:
    """DNS性能测试工具，用于测试不同参数下的性能表现"""
    
    def __init__(self, test_domains_file=None, output_dir="test_results", config=None):
        # 固定测试数据
        self.test_domains = []
        self.load_test_domains(test_domains_file)
        
        # 确保结果目录存在
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        # 使用传入的配置或创建新配置
        self.config = config
        
        # 初始默认参数
        self.default_params = {
            'QueriesPerSecond': self.config.getint('DNS', 'QueriesPerSecond') if config else 12,
            'MaxWorkers': self.config.getint('DNS', 'MaxWorkers') if config else 12,
            'Timeout': self.config.getfloat('DNS', 'Timeout') if config else 1,
            'BatchSize': self.config.getint('DNS', 'BatchSize') if config else 100,
            'CollectThreads': self.config.getint('Crawler', 'CollectThreads') if config else 5
        }
        
        # 参数测试范围
        self.param_ranges = {
            'QueriesPerSecond': [5, 10, 15, 20, 25, 30],
            'MaxWorkers': [5, 10, 15, 20, 30, 50],
            'Timeout': [0.5, 1, 2, 3, 5],
            'BatchSize': [50, 100, 200, 500],
            'CollectThreads': [3, 5, 10, 15, 20]
        }
        
        # 参数名称映射
        self.param_names = {
            'QueriesPerSecond': '每秒查询次数 (QueriesPerSecond)',
            'MaxWorkers': '最大线程数 (MaxWorkers)',
            'Timeout': '查询超时时间 (Timeout)',
            'BatchSize': '批处理大小 (BatchSize)',
            'CollectThreads': '域名收集线程数 (CollectThreads)'
        }
        
        # 参数简称映射
        self.param_short_names = {
            'QueriesPerSecond': '每秒查询次数',
            'MaxWorkers': '最大线程数',
            'Timeout': '超时时间(秒)',
            'BatchSize': '批处理大小',
            'CollectThreads': '收集线程数'
        }
        
        # 性能测试结果
        self.results = []
        self.all_param_results = {}
        
        # 速率限制器
        self.query_limiter = None
    
    def load_test_domains(self, file_path=None):
        """加载测试域名"""
        # 如果提供了文件，从文件加载域名
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.test_domains = data
                    elif isinstance(data, dict) and 'domains' in data:
                        self.test_domains = data['domains']
                    print(f"从文件加载了 {len(self.test_domains)} 个测试域名")
            except Exception as e:
                print(f"加载测试域名文件出错: {e}")
        
        # 如果没有加载到域名或没提供文件，使用默认域名
        if not self.test_domains:
            # 使用一些常用域名作为测试数据
            self.test_domains = [
                "baidu.com", "qq.com", "163.com", "taobao.com", "jd.com",
                "weibo.com", "sina.com.cn", "sohu.com", "douyin.com", "zhihu.com",
                "bilibili.com", "360.cn", "csdn.net", "github.com", "aliyun.com",
                "tencent.com", "ctrip.com", "xinhuanet.com", "huawei.com", "mi.com"
            ]
            
            # 为了获得更多测试数据，添加子域名变体
            domain_variants = []
            prefixes = ["www", "mail", "blog", "news", "shop", "m", "api", "dev"]
            for domain in self.test_domains[:]:
                for prefix in prefixes:
                    domain_variants.append(f"{prefix}.{domain}")
            
            # 合并原始域名和变体
            self.test_domains.extend(domain_variants)
            print(f"使用 {len(self.test_domains)} 个默认测试域名")

    class QueryRateLimiter:
        """查询速率限制器，确保每秒不超过指定次数的查询"""
        def __init__(self, queries_per_second):
            self.queries_per_second = queries_per_second
            self.query_times = []
            self.lock = threading.Lock()
        
        def wait_if_needed(self):
            """如果需要，等待以满足速率限制"""
            with self.lock:
                current_time = time.time()
                
                # 移除一秒前的查询记录
                self.query_times = [t for t in self.query_times if current_time - t < 1.0]
                
                # 如果当前查询次数已达到限制，则等待
                if len(self.query_times) >= self.queries_per_second:
                    sleep_time = 1.0 - (current_time - self.query_times[0])
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                
                # 记录当前查询时间
                self.query_times.append(time.time())
    
    def query_dns(self, domain, timeout=1.0, rate_limiter=None):
        """查询域名的DNS记录"""
        # 应用速率限制
        if rate_limiter:
            rate_limiter.wait_if_needed()
        
        start_time = time.time()
        result = {
            'domain': domain,
            'success': False,
            'query_time': 0,
            'error': None
        }
        
        try:
            # 首先尝试使用socket
            socket.gethostbyname(domain)
            result['success'] = True
        except:
            try:
                # 尝试使用dns.resolver
                resolver = dns.resolver.Resolver()
                resolver.timeout = timeout
                resolver.lifetime = timeout
                answers = resolver.resolve(domain, 'A')
                result['success'] = True
            except Exception as e:
                result['error'] = str(e)
        
        # 计算查询时间
        result['query_time'] = time.time() - start_time
        return result
    
    def test_parameter(self, param_name, param_value):
        """测试单个参数的性能"""
        # 创建一个基于默认参数的测试配置
        test_params = copy.deepcopy(self.default_params)
        test_params[param_name] = param_value
        
        # 随机选择一部分域名进行测试，以控制测试时间
        test_sample = random.sample(self.test_domains, min(100, len(self.test_domains)))
        
        print(f"测试参数 {self.param_names[param_name]} = {param_value}, 使用 {len(test_sample)} 个域名...")
        
        # 设置速率限制器
        self.query_limiter = self.QueryRateLimiter(test_params['QueriesPerSecond'])
        
        # 设置DNS超时
        timeout = test_params['Timeout']
        
        # 记录开始时间
        start_time = time.time()
        
        # 并行查询DNS
        results = []
        with ThreadPoolExecutor(max_workers=test_params['MaxWorkers']) as executor:
            # 分批处理
            batch_size = test_params['BatchSize']
            for i in range(0, len(test_sample), batch_size):
                batch = test_sample[i:i+batch_size]
                
                # 提交批量查询任务
                futures = []
                for domain in batch:
                    future = executor.submit(self.query_dns, domain, timeout, self.query_limiter)
                    futures.append(future)
                
                # 获取结果
                for future in futures:
                    result = future.result()
                    results.append(result)
        
        # 计算性能指标
        total_time = time.time() - start_time
        successful_queries = sum(1 for r in results if r['success'])
        success_rate = successful_queries / len(test_sample) if test_sample else 0
        
        # 计算查询时间统计数据
        query_times = [r['query_time'] for r in results]
        avg_query_time = statistics.mean(query_times) if query_times else 0
        
        try:
            median_query_time = statistics.median(query_times) if query_times else 0
        except:
            median_query_time = 0
        
        # 每秒查询数
        queries_per_second = len(test_sample) / total_time if total_time > 0 else 0
        
        # 记录测试结果
        test_result = {
            'param_name': param_name,
            'param_value': param_value,
            'total_time': total_time,
            'success_rate': success_rate,
            'avg_query_time': avg_query_time,
            'median_query_time': median_query_time,
            'queries_per_second': queries_per_second,
            'sample_size': len(test_sample)
        }
        
        print(f"  总耗时: {total_time:.2f}秒, 成功率: {success_rate:.2%}, 平均查询时间: {avg_query_time:.4f}秒, 每秒查询数: {queries_per_second:.2f}")
        self.results.append(test_result)
        
        return test_result
    
    def run_tests(self):
        """运行所有参数测试"""
        print("开始DNS缓存工具参数性能测试...\n")
        
        # 为每个参数测试不同的值
        for param_name, values in self.param_ranges.items():
            print(f"\n测试参数: {self.param_names[param_name]}")
            print("="*50)
            
            param_results = []
            for value in values:
                test_result = self.test_parameter(param_name, value)
                param_results.append(test_result)
            
            # 找出这个参数的最佳值
            best_result = max(param_results, key=lambda x: x['queries_per_second'] * x['success_rate'])
            self.default_params[param_name] = best_result['param_value']
            
            print(f"\n最佳{self.param_names[param_name]}值: {best_result['param_value']}")
            print(f"  查询速度: {best_result['queries_per_second']:.2f}/秒, 成功率: {best_result['success_rate']:.2%}")
            
            # 保存这个参数的单独测试结果
            self.save_param_results(param_name, param_results)
        
        # 保存最终的最佳参数
        self.save_best_params()
    
    def save_param_results(self, param_name, results):
        """保存单个参数的测试结果"""
        file_path = os.path.join(self.output_dir, f"param_test_{param_name}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        print(f"参数 {self.param_names[param_name]} 的测试结果已保存到: {file_path}")
        
        # 存储测试结果用于生成汇总报告
        self.all_param_results[param_name] = results
    
    def save_readable_results(self):
        """将JSON测试结果转换为易读的TXT格式"""
        output_file = os.path.join(self.output_dir, "dns_performance_test_results.txt")
        
        with open(output_file, "w", encoding="utf-8") as out_file:
            out_file.write("DNS缓存工具性能测试结果\n")
            out_file.write("=" * 50 + "\n\n")
            
            # 首先显示最佳参数组合
            out_file.write("【最佳参数组合】\n")
            out_file.write("-" * 30 + "\n")
            for param, value in self.default_params.items():
                param_name = self.param_short_names.get(param, param)
                out_file.write(f"{param_name}: {value}\n")
            out_file.write("\n")
            
            # 显示各个参数的测试结果
            for param_name, results in self.all_param_results.items():
                short_name = self.param_short_names.get(param_name, param_name)
                out_file.write(f"【{short_name}参数测试结果】\n")
                out_file.write("-" * 30 + "\n")
                out_file.write(f"{'参数值':<10}{'总耗时(秒)':<15}{'成功率':<10}{'每秒查询数':<15}\n")
                
                # 按性能指标(每秒查询数*成功率)排序
                sorted_results = sorted(results, key=lambda x: x.get('queries_per_second', 0) * x.get('success_rate', 0), reverse=True)
                
                for result in sorted_results:
                    param_value = result.get('param_value', 'N/A')
                    total_time = f"{result.get('total_time', 0):.2f}"
                    success_rate = f"{result.get('success_rate', 0)*100:.1f}%"
                    qps = f"{result.get('queries_per_second', 0):.2f}"
                    
                    out_file.write(f"{param_value:<10}{total_time:<15}{success_rate:<10}{qps:<15}\n")
                
                out_file.write("\n")
            
            # 测试结论
            out_file.write("测试结论\n")
            out_file.write("-" * 30 + "\n")
            out_file.write("以上参数组合在当前系统和网络环境下经过测试后得出的最佳性能参数设置。\n")
            out_file.write("使用这些参数可以在保持较高DNS查询成功率的同时，获得最优的查询性能。\n\n")
            out_file.write(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        print(f"\n测试结果已转换为易读格式，保存至: {output_file}")
        return output_file
    
    def save_best_params(self):
        """保存最佳参数组合"""
        file_path = os.path.join(self.output_dir, "best_params.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.default_params, f, indent=2)
        
        # 同时创建一个配置文件格式的版本
        config_content = """[General]
TargetCount = 2000
DataDirectory = data

[DNS]
QueriesPerSecond = {QueriesPerSecond}
MaxWorkers = {MaxWorkers}
Timeout = {Timeout}
BatchSize = {BatchSize}

[Crawler]
ParseJavaScript = false
ParseCSS = false
ParseImages = false
ParseMetaTags = false
UserAgent = Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36
Timeout = 10
CollectThreads = {CollectThreads}

[Export]
DefaultFormat = json
IncludeDNSInfo = true
""".format(**self.default_params)
        
        config_path = os.path.join(self.output_dir, "optimal_config.ini")
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        # 生成易读的TXT格式测试结果
        readable_result_file = self.save_readable_results()
        
        print(f"\n最佳参数已保存到: {file_path}")
        print(f"优化后的配置文件已保存到: {config_path}")
        print(f"易读格式的测试结果已保存到: {readable_result_file}")
        
        # 打印最终推荐
        self.print_recommendations()
    
    def print_recommendations(self):
        """打印最终推荐的参数设置"""
        print("\n" + "="*60)
        print("DNS缓存工具性能测试完成，推荐参数设置:")
        print("="*60)
        
        print(f"每秒查询次数 (QueriesPerSecond): {self.default_params['QueriesPerSecond']}")
        print(f"最大线程数 (MaxWorkers): {self.default_params['MaxWorkers']}")
        print(f"DNS查询超时时间 (Timeout): {self.default_params['Timeout']}秒")
        print(f"批处理大小 (BatchSize): {self.default_params['BatchSize']}个域名")
        print(f"域名收集线程数 (CollectThreads): {self.default_params['CollectThreads']}")
        
        print("\n这些参数在当前系统和网络环境下应该具有最佳性能。")
        
        # 询问用户是否应用设置
        config_path = os.path.join(self.output_dir, "optimal_config.ini")
        target_config = "config.ini"
        
        while True:
            user_input = input(f"\n是否将优化配置 {config_path} 复制到程序目录并重命名为 {target_config}？(y/n): ")
            if user_input.lower() in ['y', 'yes', '是', '是的']:
                try:
                    import shutil
                    shutil.copy2(config_path, target_config)
                    print(f"已成功将配置文件复制为 {target_config}")
                    
                    # 更新当前配置
                    if self.config:
                        self.config.load_config()
                        print("配置已重新加载，新设置将在下次操作时生效")
                except Exception as e:
                    print(f"复制配置文件时出错: {e}")
                break
            elif user_input.lower() in ['n', 'no', '否', '不']:
                print(f"配置文件未应用，您可以稍后手动复制 {config_path} 到程序目录并重命名为 {target_config}")
                break
            else:
                print("无效的输入，请输入 y 或 n")

class DNSCacheTool:
    def __init__(self):
        # 加载配置
        self.config = Config()
        
        self.visited_domains = set()
        self.domains_to_visit = set()
        self.collected_domains = set()
        self.dns_results = {}  # 存储DNS解析结果
        self.only_subdomains = False  # 是否只收集子域名
        self.base_domain = None  # 基础域名
        self.current_source_file = None  # 当前使用的源文件
        
        # 从配置中读取设置
        self.target_count = self.config.getint('General', 'TargetCount')
        self.data_dir = self.config.get('General', 'DataDirectory')
        self.current_file = None
        self.rate_limiter = DNSRateLimiter(
            queries_per_second=self.config.getint('DNS', 'QueriesPerSecond')
        )
        
        # 创建数据目录
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
    
    def extract_domain(self, url):
        """从URL中提取域名"""
        try:
            if not url.startswith('http'):
                url = 'http://' + url
            parsed = urlparse(url)
            domain = parsed.netloc
            # 移除端口号
            if ':' in domain:
                domain = domain.split(':')[0]
            return domain.lower() if domain else None
        except Exception as e:
            print(f"解析URL时出错: {url}, 错误: {e}")
            return None
    
    def is_subdomain(self, domain):
        """判断域名是否为指定基础域名的子域名"""
        if not self.only_subdomains or not self.base_domain:
            return True  # 如果不限制子域名，则返回True
        
        # 检查domain是否以base_domain结尾
        return domain.endswith('.' + self.base_domain) or domain == self.base_domain
    
    def get_links_from_domain(self, domain):
        """获取域名页面上的所有链接并增强域名提取能力"""
        links = set()
        try:
            headers = {
                'User-Agent': self.config.get('Crawler', 'UserAgent')
            }
            url = f"http://{domain}"
            
            # 访问网页时已进行DNS解析
            response = requests.get(
                url, 
                headers=headers, 
                timeout=self.config.getint('Crawler', 'Timeout')
            )
            
            # 记录自动完成的DNS解析结果
            try:
                ip_address = socket.gethostbyname(domain)
                result = {
                    'domain': domain,
                    'success': True,
                    'ip_addresses': [ip_address],
                    'timestamp': time.time(),
                    'error': None
                }
                self.dns_results[domain] = result
            except Exception as dns_error:
                # DNS解析失败但网页访问成功的情况（极少发生）
                pass
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 1. 从<a>标签提取链接
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                extracted_domain = self.extract_domain(href)
                if extracted_domain and extracted_domain != domain:
                    if self.is_subdomain(extracted_domain):
                        links.add(extracted_domain)
            
            # 2. 如果配置允许，从<script>标签的src属性中提取域名
            if self.config.getboolean('Crawler', 'ParseJavaScript'):
                for script_tag in soup.find_all('script', src=True):
                    src = script_tag['src']
                    if src:
                        # 处理相对URL
                        full_url = urljoin(url, src)
                        extracted_domain = self.extract_domain(full_url)
                        if extracted_domain and extracted_domain != domain:
                            if self.is_subdomain(extracted_domain):
                                links.add(extracted_domain)
            
            # 3. 如果配置允许，从<link>标签（CSS文件）中提取域名
            if self.config.getboolean('Crawler', 'ParseCSS'):
                for link_tag in soup.find_all('link', href=True):
                    href = link_tag['href']
                    if href:
                        # 处理相对URL
                        full_url = urljoin(url, href)
                        extracted_domain = self.extract_domain(full_url)
                        if extracted_domain and extracted_domain != domain:
                            if self.is_subdomain(extracted_domain):
                                links.add(extracted_domain)
            
            # 4. 如果配置允许，从<img>标签的src属性中提取域名
            if self.config.getboolean('Crawler', 'ParseImages'):
                for img_tag in soup.find_all('img', src=True):
                    src = img_tag['src']
                    if src:
                        # 处理相对URL
                        full_url = urljoin(url, src)
                        extracted_domain = self.extract_domain(full_url)
                        if extracted_domain and extracted_domain != domain:
                            if self.is_subdomain(extracted_domain):
                                links.add(extracted_domain)
            
            # 5. 如果配置允许，从<meta>标签中提取域名
            if self.config.getboolean('Crawler', 'ParseMetaTags'):
                for meta_tag in soup.find_all('meta', content=True):
                    content = meta_tag['content']
                    if content and ('http://' in content or 'https://' in content):
                        extracted_domain = self.extract_domain(content)
                        if extracted_domain and extracted_domain != domain:
                            if self.is_subdomain(extracted_domain):
                                links.add(extracted_domain)
            
            # 6. 从JavaScript文件中提取URL模式
            if self.config.getboolean('Crawler', 'ParseJavaScript'):
                for script in soup.find_all('script'):
                    if script.string:
                        # 使用正则表达式匹配URL
                        js_content = script.string
                        # 匹配双引号或单引号中的URL
                        url_patterns = re.findall(r'["\']https?://([^/\'"]+)[\'"]', js_content)
                        for pattern in url_patterns:
                            if pattern and pattern != domain:
                                if self.is_subdomain(pattern):
                                    links.add(pattern)
            
        except Exception as e:
            print(f"获取域名 {domain} 链接时出错: {e}")
            # 记录失败的DNS解析
            result = {
                'domain': domain,
                'success': False,
                'ip_addresses': [],
                'timestamp': time.time(),
                'error': str(e)
            }
            self.dns_results[domain] = result
        
        return links
    
    def query_dns(self, domain):
        """查询域名的DNS记录并存储结果"""
        # 应用速率限制
        self.rate_limiter.wait_if_needed()
        
        result = {
            'domain': domain,
            'success': False,
            'ip_addresses': [],
            'timestamp': time.time(),
            'error': None
        }
        
        try:
            ip = socket.gethostbyname(domain)
            result['success'] = True
            result['ip_addresses'].append(ip)
        except Exception as socket_error:
            try:
                resolver = dns.resolver.Resolver()
                resolver.timeout = self.config.getfloat('DNS', 'Timeout')
                resolver.lifetime = self.config.getfloat('DNS', 'Timeout')
                answers = resolver.resolve(domain, 'A')
                
                result['success'] = True
                for rdata in answers:
                    result['ip_addresses'].append(str(rdata))
            except Exception as dns_error:
                result['success'] = False
                result['error'] = str(dns_error)
                print(f"查询DNS时出错: {domain}, 错误: {dns_error}")
        
        # 存储结果
        self.dns_results[domain] = result
        return result['success']
    
    def process_domain(self, domain):
        """处理单个域名的操作，用于多线程"""
        if domain in self.visited_domains:
            return
            
        self.visited_domains.add(domain)
        print(f"正在处理域名: {domain} [已收集: {len(self.collected_domains)}/{self.target_count}]")
        
        try:
            # 获取该域名上的链接，访问网页时系统会自动执行DNS解析
            new_links = self.get_links_from_domain(domain)
            
            with self.lock:
                # 记录成功访问的域名
                self.collected_domains.add(domain)
                
                # 添加新发现的域名到待访问列表
                new_domains = {d for d in new_links if d not in self.visited_domains}
                self.domains_to_visit.update(new_domains)
                
                # 每收集100个域名保存一次（使用临时保存，不更新文件名中的计数）
                if len(self.collected_domains) % 100 == 0:
                    print(f"已收集 {len(self.collected_domains)} 个域名")
                    self.save_domains_to_file(final_save=False)
        except Exception as e:
            print(f"处理域名 {domain} 时出错: {e}")
    
    def collect_domains(self, start_domain, only_subdomains=False):
        """从起始域名开始收集域名"""
        self.only_subdomains = only_subdomains
        self.base_domain = start_domain
        print(f"开始从 {start_domain} 收集域名...")
        
        if only_subdomains:
            print(f"🔒 仅收集 {start_domain} 的子域名")
        
        self.visited_domains = set()
        self.domains_to_visit = {start_domain}
        self.collected_domains = set()
        self.dns_results = {}
        self.lock = threading.Lock()  # 添加线程锁
        
        # 重置当前文件名，让save_domains_to_file创建新文件名
        self.current_file = None
        
        # 创建线程池
        collect_threads = self.config.getint('Crawler', 'CollectThreads')
        print(f"🧵 使用 {collect_threads} 个线程进行域名收集")
        
        with ThreadPoolExecutor(max_workers=collect_threads) as executor:
            while self.domains_to_visit and len(self.collected_domains) < self.target_count:
                # 取出一批域名进行处理
                batch_size = min(collect_threads * 2, len(self.domains_to_visit))
                domains_batch = []
                
                for _ in range(batch_size):
                    if not self.domains_to_visit:
                        break
                    domains_batch.append(self.domains_to_visit.pop())
                
                # 提交到线程池
                futures = [executor.submit(self.process_domain, domain) for domain in domains_batch]
                
                # 等待所有线程完成
                for future in futures:
                    future.result()
        
        # 最终保存，更新域名数量
        self.save_domains_to_file(final_save=True)
        print(f"域名收集完成! 共收集了 {len(self.collected_domains)} 个域名")
    
    def batch_query_dns(self, file_path=None):
        """批量查询DNS以加快缓存"""
        domains = self.load_domains_from_file(file_path) if file_path else self.collected_domains
        
        if not domains:
            print("没有域名可供查询!")
            return
        
        # 记录来源文件，用于生成更有描述性的导出文件名
        if file_path:
            self.current_source_file = file_path
        else:
            self.current_source_file = None
        
        # 清空之前的DNS结果
        self.dns_results = {}
        
        print(f"开始查询 {len(domains)} 个域名的DNS...")
        print(f"注意: 查询速率限制为每秒最多{self.config.getint('DNS', 'QueriesPerSecond')}次查询")
        
        success_count = 0
        total_count = len(domains)
        
        # 使用限制线程数的线程池来控制并发查询
        max_workers = min(self.config.getint('DNS', 'MaxWorkers'), len(domains))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            domains_list = list(domains)
            batch_size = self.config.getint('DNS', 'BatchSize')  # 每批处理的域名数量
            
            for i in range(0, len(domains_list), batch_size):
                batch = domains_list[i:i+batch_size]
                results = list(executor.map(self.query_dns, batch))
                batch_success = sum(1 for r in results if r)
                success_count += batch_success
                
                # 打印进度
                progress = min(100, int((i + len(batch)) / total_count * 100))
                print(f"进度: {progress}%, 成功: {success_count}/{i+len(batch)}")
        
        print(f"DNS查询完成! 成功查询了 {success_count}/{total_count} 个域名")
        
        # 询问是否导出结果
        self.ask_export_results()
    
    def ask_export_results(self):
        """询问用户是否导出结果"""
        if not self.dns_results:
            print("没有可导出的结果!")
            return
        
        while True:
            print("\n是否导出DNS查询结果?")
            print("1. 📊 导出为JSON格式")
            print("2. 📈 导出为CSV格式")
            print("3. ❌ 不导出")
            
            choice = input("\n请选择 (1-3): ")
            
            if choice == '1':
                self.export_results('json')
                break
            elif choice == '2':
                self.export_results('csv')
                break
            elif choice == '3':
                break
            else:
                print("无效的选择! 请重试。")
    
    def export_results(self, format_type):
        """导出DNS查询结果"""
        if not self.dns_results:
            print("没有结果可导出!")
            return
        
        timestamp = time.strftime("%Y%m%d%H%M")
        
        # 创建更有描述性的文件名
        filename_parts = []
        successful_domains = [domain for domain, result in self.dns_results.items() if result['success']]
        
        # 添加源文件或域名信息
        if hasattr(self, 'base_domain') and self.base_domain:
            # 如果是从特定域名收集的
            base_name = self.base_domain.replace('.', '_')
            filename_parts.append(base_name)
            
            if hasattr(self, 'only_subdomains') and self.only_subdomains:
                filename_parts.append("仅子域名")
        elif hasattr(self, 'current_source_file') and self.current_source_file:
            # 如果是从文件加载的
            source_filename = os.path.basename(self.current_source_file)
            source_name = os.path.splitext(source_filename)[0]
            filename_parts.append(f"来源_{source_name}")
        
        # 添加成功查询数量信息
        filename_parts.append(f"{len(successful_domains)}个成功DNS结果")
        
        # 合并所有部分
        descriptive_name = "-".join(filename_parts) if filename_parts else "dns_results"
        
        if format_type.lower() == 'json':
            # 导出为JSON，只包含域名列表
            export_file = os.path.join(self.data_dir, f"{descriptive_name}_{timestamp}.json")
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(successful_domains, f, ensure_ascii=False, indent=2)
                
        elif format_type.lower() == 'csv':
            # 导出为CSV
            export_file = os.path.join(self.data_dir, f"{descriptive_name}_{timestamp}.csv")
            with open(export_file, 'w', encoding='utf-8', newline='') as f:
                csv_writer = csv.writer(f)
                # 写入表头
                csv_writer.writerow(['域名', '解析状态', 'IP地址'])
                
                # 写入数据
                for domain, result in self.dns_results.items():
                    ip_addresses = ';'.join(result['ip_addresses']) if result['ip_addresses'] else ''
                    csv_writer.writerow([
                        domain,
                        '成功' if result['success'] else '失败',
                        ip_addresses
                    ])
        else:
            print(f"不支持的导出格式: {format_type}")
            return
        
        print(f"结果已导出到: {export_file}")
        return export_file
    
    def save_domains_to_file(self, final_save=False):
        """保存域名列表到文件
        
        参数:
            final_save (bool): 是否是最终保存，为True时会更新文件名中的域名数量
        """
        if not self.collected_domains:
            print("没有域名可保存!")
            return
        
        # 如果是最终保存或者当前文件未创建，则创建/更新文件名
        if final_save or not self.current_file:
            timestamp = time.strftime("%Y%m%d%H%M")
            
            # 创建更有描述性的文件名
            filename_parts = []
            
            # 添加起始域名信息
            if hasattr(self, 'base_domain') and self.base_domain:
                base_name = self.base_domain.replace('.', '_')
                filename_parts.append(base_name)
            
            # 添加是否只包含子域名信息
            if hasattr(self, 'only_subdomains') and self.only_subdomains:
                filename_parts.append("仅子域名")
            
            # 添加域名数量
            filename_parts.append(f"{len(self.collected_domains)}个域名")
            
            # 合并所有部分
            descriptive_name = "-".join(filename_parts) if filename_parts else "domains"
            
            # 完整文件名
            new_file = os.path.join(self.data_dir, f"{descriptive_name}_{timestamp}.json")
            
            # 如果已有文件且文件名不同，则需要更新（重命名或创建新文件）
            if self.current_file and self.current_file != new_file and os.path.exists(self.current_file):
                # 如果是最终保存，尝试删除旧文件
                if final_save:
                    try:
                        os.remove(self.current_file)
                        print(f"已删除旧文件: {self.current_file}")
                    except Exception as e:
                        print(f"删除旧文件时出错: {e}")
            
            self.current_file = new_file
        
        # 简化的格式，仅保存域名列表
        domains_data = list(self.collected_domains)
        
        with open(self.current_file, 'w', encoding='utf-8') as f:
            json.dump(domains_data, f, ensure_ascii=False, indent=2)
        
        print(f"域名已保存到文件: {self.current_file}")
        return self.current_file
    
    def load_domains_from_file(self, file_path):
        """从文件加载域名列表"""
        try:
            # 记录来源文件
            self.current_source_file = file_path
            
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    # 加载JSON格式
                    data = json.load(f)
                    
                    # 检查是否是直接的域名列表（新格式）
                    if isinstance(data, list):
                        domains = data
                        print(f"从文件 {file_path} 加载了 {len(domains)} 个域名")
                    
                    # 检查是否是旧的复杂格式
                    elif isinstance(data, dict) and 'domains' in data:
                        domains = data['domains']
                        print(f"从文件 {file_path} 加载了 {len(domains)} 个域名 (旧格式)")
                        
                        # 加载子域名设置
                        if 'only_subdomains' in data and 'base_domain' in data:
                            self.only_subdomains = data['only_subdomains']
                            self.base_domain = data['base_domain']
                            if self.only_subdomains and self.base_domain:
                                print(f"该文件仅包含 {self.base_domain} 的子域名")
                        
                        # 如果文件包含DNS结果信息，也加载
                        if 'dns_results' in data:
                            self.dns_results = data['dns_results']
                            print(f"同时加载了 {len(self.dns_results)} 条DNS查询结果")
                    
                    # 其他格式
                    else:
                        domains = data
                        print(f"从文件 {file_path} 加载了 {len(domains)} 个域名")
                        
                except:
                    # 尝试读取CSV格式
                    f.seek(0)  # 重置文件指针
                    if file_path.endswith('.csv'):
                        csv_reader = csv.reader(f)
                        next(csv_reader)  # 跳过表头
                        domains = []
                        for row in csv_reader:
                            if row and len(row) > 0:
                                domains.append(row[0])  # 假设第一列是域名
                        print(f"从CSV文件 {file_path} 加载了 {len(domains)} 个域名")
                    else:
                        raise ValueError("无法识别的文件格式")
                
                self.collected_domains = set(domains)
                return set(domains)
        except Exception as e:
            print(f"加载域名文件时出错: {e}")
            return set()
    
    def import_domains(self):
        """导入域名列表"""
        print("\n📥 导入域名列表")
        print("支持的格式: JSON文件或CSV文件（第一列为域名）")
        
        file_path = input("请输入文件路径: ")
        
        if not os.path.exists(file_path):
            print("❌ 文件不存在!")
            return
        
        domains = self.load_domains_from_file(file_path)
        if domains:
            print(f"✅ 成功导入 {len(domains)} 个域名")
            
            # 询问是否进行DNS查询
            if input("\n是否对这些域名进行DNS查询? (y/n): ").lower() == 'y':
                self.batch_query_dns()
    
    def get_available_files(self):
        """获取可用的域名文件列表"""
        files = []
        for file in os.listdir(self.data_dir):
            if (file.startswith("domains_") and file.endswith(".json")) or \
               (file.startswith("dns_results_") and (file.endswith(".json") or file.endswith(".csv"))):
                files.append(os.path.join(self.data_dir, file))
        return files
    
    def edit_config(self):
        """编辑配置"""
        while True:
            print("\n" + "="*50)
            print("⚙️ 配置设置")
            print("="*50)
            
            sections = self.config.config.sections()
            for i, section in enumerate(sections, 1):
                if section == 'General':
                    icon = "🔧"
                    name = "常规设置"
                elif section == 'DNS':
                    icon = "🌐"
                    name = "DNS查询设置"
                elif section == 'Crawler':
                    icon = "🕸️"
                    name = "网页爬取设置"
                elif section == 'Export':
                    icon = "📤"
                    name = "导出设置"
                else:
                    icon = "📝"
                    name = section
                print(f"{i}. {icon} {name}")
            print(f"{len(sections)+1}. 💾 保存并返回")
            
            try:
                choice = int(input("\n请选择要编辑的部分: "))
                
                if 1 <= choice <= len(sections):
                    section = sections[choice-1]
                    self.edit_section(section)
                elif choice == len(sections)+1:
                    self.config.save_config()
                    break
                else:
                    print("❌ 无效的选择!")
            except ValueError:
                print("❌ 请输入有效的数字!")
    
    def edit_section(self, section):
        """编辑特定配置部分"""
        # 直接翻译配置项
        key_translations = {
            'targetcount': '目标域名数量',
            'datadirectory': '数据存储目录',
            'queriespersecond': '每秒查询次数',
            'maxworkers': '最大线程数',
            'timeout': '超时时间(秒)',
            'batchsize': '批处理大小',
            'parsejavascript': '解析JavaScript文件',
            'parsecss': '解析CSS文件',
            'parseimages': '解析图片链接',
            'parsemetatags': '解析Meta标签',
            'useragent': '浏览器标识',
            'collectthreads': '域名收集线程数',
            'defaultformat': '默认导出格式',
            'includednsinfo': '包含DNS查询结果'
        }
        
        # 直接翻译描述
        desc_translations = {
            'targetcount': '要收集的域名总数',
            'datadirectory': '用于存储域名文件的目录',
            'queriespersecond': 'DNS查询速率限制（每秒最多查询次数）',
            'maxworkers': 'DNS查询使用的最大线程数',
            'timeout': 'DNS查询和网页请求的超时时间',
            'batchsize': '每批处理的域名数量',
            'parsejavascript': '是否从JavaScript文件中提取域名（true/false）',
            'parsecss': '是否从CSS文件中提取域名（true/false）',
            'parseimages': '是否从图片链接中提取域名（true/false）',
            'parsemetatags': '是否从Meta标签中提取域名（true/false）',
            'useragent': '访问网页时使用的浏览器标识',
            'collectthreads': '域名收集过程使用的线程数',
            'defaultformat': '默认的结果导出格式（json/csv）',
            'includednsinfo': '保存域名文件时是否包含DNS查询结果（true/false）'
        }
            
        while True:
            section_name = self.config.get_name(section)
            print(f"\n📝 编辑 {section_name} 配置")
            print("="*50)
            
            options = self.config.config.options(section)
            for i, option in enumerate(options, 1):
                value = self.config.get(section, option)
                # 直接使用翻译字典
                option_chinese_name = key_translations.get(option.lower(), option)
                option_desc = desc_translations.get(option.lower(), "")
                print(f"{i}. {option_chinese_name} = {value}")
                if option_desc:
                    print(f"   - {option_desc}")
            print(f"{len(options)+1}. ⬅️ 返回上级菜单")
            
            try:
                choice = int(input("\n请选择要编辑的选项: "))
                
                if 1 <= choice <= len(options):
                    option = options[choice-1]
                    # 直接使用翻译字典
                    option_chinese_name = key_translations.get(option.lower(), option)
                    current_value = self.config.get(section, option)
                    option_desc = desc_translations.get(option.lower(), "")
                    if option_desc:
                        print(f"描述: {option_desc}")
                    new_value = input(f"请输入新的{option_chinese_name}的值 (当前值: {current_value}): ")
                    self.config.set(section, option, new_value)
                    print(f"✅ 已更新 {option_chinese_name} = {new_value}")
                elif choice == len(options)+1:
                    break
                else:
                    print("❌ 无效的选择!")
            except ValueError:
                print("❌ 请输入有效的数字!")

    def run_performance_test(self):
        """运行性能测试，找出最佳参数配置"""
        print("\n" + "="*50)
        print("🚀 DNS缓存工具参数性能测试")
        print("="*50)
        
        # 询问是否使用当前域名数据
        use_current_domains = False
        test_file = None
        
        if self.collected_domains:
            while True:
                choice = input(f"是否使用当前已收集的 {len(self.collected_domains)} 个域名进行测试？(y/n): ")
                if choice.lower() in ['y', 'yes', '是', '是的']:
                    use_current_domains = True
                    
                    # 保存当前域名到临时文件
                    temp_file = os.path.join(self.data_dir, "temp_test_domains.json")
                    with open(temp_file, 'w', encoding='utf-8') as f:
                        json.dump(list(self.collected_domains), f)
                    test_file = temp_file
                    print(f"已将当前域名保存到临时文件: {temp_file}")
                    break
                elif choice.lower() in ['n', 'no', '否', '不']:
                    break
                else:
                    print("无效的输入，请输入 y 或 n")
        
        # 如果不使用当前域名，询问是否使用已有文件
        if not use_current_domains:
            files = self.get_available_files()
            if files:
                print("\n📂 可以使用的域名文件:")
                for i, file in enumerate(files, 1):
                    print(f"{i}. {os.path.basename(file)}")
                print(f"{len(files)+1}. 使用默认测试域名")
                
                while True:
                    try:
                        choice = int(input("\n请选择要使用的文件 (输入序号): "))
                        if 1 <= choice <= len(files):
                            test_file = files[choice-1]
                            print(f"选择了文件: {test_file}")
                            break
                        elif choice == len(files)+1:
                            print("将使用默认测试域名")
                            break
                        else:
                            print("无效的选择，请重试")
                    except ValueError:
                        print("请输入有效的数字!")
        
        # 创建并运行性能测试器
        tester = DNSPerformanceTester(test_file, "test_results", self.config)
        tester.run_tests()
        
        # 清理临时文件
        if use_current_domains and os.path.exists(test_file):
            try:
                os.remove(test_file)
                print(f"已删除临时文件: {test_file}")
            except:
                pass
        
        input("\n按Enter键返回主菜单...")

def main():
    tool = DNSCacheTool()
    
    while True:
        print("\n" + "="*50)
        print("🌐 DNS缓存工具 🚀")
        print("="*50)
        print("1. 🔍 从新域名开始收集")
        print("2. 🔄 使用已有域名文件查询DNS")
        print("3. 📥 导入域名列表")
        print("4. 📤 导出上次查询结果")
        print("5. ⚙️ 配置设置")
        print("6. 🚀 运行性能测试")
        print("7. 👋 退出")
        
        choice = input("\n请选择操作: ")
        
        if choice == '1':
            start_domain = input("请输入起始域名 (例如: example.com): ")
            if not start_domain:
                print("❌ 域名不能为空!")
                continue
            
            # 询问是否只收集子域名
            only_subdomains_choice = input(f"是否只收集 {start_domain} 的子域名? (y/n): ").lower()
            only_subdomains = only_subdomains_choice == 'y'
            
            tool.current_file = None  # 重置当前文件，将创建新文件
            tool.collect_domains(start_domain, only_subdomains)
        
        elif choice == '2':
            files = tool.get_available_files()
            
            if not files:
                print("❌ 没有找到域名文件! 请先收集域名。")
                continue
            
            print("\n📂 可用的文件:")
            for i, file in enumerate(files, 1):
                print(f"{i}. {os.path.basename(file)}")
            
            try:
                file_index = int(input("\n请选择文件 (输入序号): ")) - 1
                if 0 <= file_index < len(files):
                    tool.batch_query_dns(files[file_index])
                else:
                    print("❌ 无效的选择!")
            except ValueError:
                print("❌ 请输入有效的序号!")
        
        elif choice == '3':
            tool.import_domains()
        
        elif choice == '4':
            if not tool.dns_results:
                print("❌ 没有可导出的DNS查询结果! 请先进行查询。")
                continue
            
            tool.ask_export_results()
        
        elif choice == '5':
            tool.edit_config()
        
        elif choice == '6':
            tool.run_performance_test()
        
        elif choice == '7':
            print("👋 感谢使用! 再见!")
            break
        
        else:
            print("❌ 无效的选择! 请重试。")

if __name__ == "__main__":
    main() 
