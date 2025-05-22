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
        
        self.load_config() # 在__init__中，我们通常不直接向Config()的调用者返回状态。
                           # 如果调用者需要状态和消息，可以再次调用load_config()。
    
    def load_config(self) -> tuple[bool, str]:
        """加载配置文件。返回 (success_status, message)。"""
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
                return True, f"已加载配置文件: {self.config_file}" 
            except Exception as e:
                return False, f"加载配置文件出错: {e}" 
        else:
            # 保存默认配置
            created, message = self.save_config() 
            if created:
                return True, f"已创建默认配置文件: {self.config_file}" 
            else:
                return False, f"创建默认配置文件失败: {message}" 
    
    def save_config(self) -> tuple[bool, str]:
        """保存配置到文件。返回 (success_status, message)。"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            return True, f"配置已保存到: {self.config_file}" 
        except Exception as e:
            return False, f"保存配置文件时出错: {e}" 
    
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
    
    def __init__(self, test_domains_file=None, output_dir="test_results", config=None, output_callback=None): # 添加了 output_callback
        self.output_callback = output_callback
        # 固定测试数据
        self.test_domains = []
        self.load_test_domains(test_domains_file) # load_test_domains 将使用 output_callback
        
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
                    if self.output_callback: self.output_callback(f"从文件加载了 {len(self.test_domains)} 个测试域名: {file_path}")
            except Exception as e:
                if self.output_callback: self.output_callback(f"加载测试域名文件 {file_path} 出错: {e}", is_error=True)
                pass # 如果文件加载失败，允许继续使用默认域名
        
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
            if self.output_callback: self.output_callback(f"使用 {len(self.test_domains)} 个默认测试域名")

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
        sample_size = min(100, len(self.test_domains))
        if not self.test_domains: 
            test_sample = []
            if self.output_callback: self.output_callback("警告: 测试域名列表为空。", is_error=True)
        else:
            test_sample = random.sample(self.test_domains, sample_size)
        
        if self.output_callback: self.output_callback(f"测试参数 {self.param_names[param_name]} = {param_value}, 使用 {len(test_sample)} 个域名...")
        
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
        query_times = [r['query_time'] for r in results if r['success']] # 仅考虑成功查询的时间统计
        avg_query_time = statistics.mean(query_times) if query_times else 0
        
        try:
            median_query_time = statistics.median(query_times) if query_times else 0
        except statistics.StatisticsError: # 处理样本量过小无法计算中位数的情况
            median_query_time = avg_query_time if query_times else 0
        
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
        
        if self.output_callback: self.output_callback(f"  总耗时: {total_time:.2f}秒, 成功率: {success_rate:.2%}, 平均查询时间: {avg_query_time:.4f}秒, 每秒查询数: {queries_per_second:.2f}")
        self.results.append(test_result)
        
        return test_result
    
    def run_tests(self) -> tuple[dict, str, str] | None: 
        """运行所有参数测试。返回 (最佳参数, 可读结果文件路径, 优化配置路径) 或 None。"""
        if self.output_callback: self.output_callback("开始DNS缓存工具参数性能测试...\n")
        
        # 为每个参数测试不同的值
        for param_name, values in self.param_ranges.items():
            if self.output_callback: self.output_callback(f"\n测试参数: {self.param_names[param_name]}\n" + "="*50)
            
            param_results = []
            for value in values:
                test_result = self.test_parameter(param_name, value) 
                param_results.append(test_result)
            
            # 找出这个参数的最佳值
            if param_results:
                 best_result_for_param = max(param_results, key=lambda x: x.get('queries_per_second', 0) * x.get('success_rate', 0))
                 if best_result_for_param: 
                    self.default_params[param_name] = best_result_for_param['param_value']
                    if self.output_callback: 
                        self.output_callback(f"\n最佳{self.param_names[param_name]}值: {best_result_for_param['param_value']}")
                        self.output_callback(f"  查询速度: {best_result_for_param.get('queries_per_second', 0):.2f}/秒, 成功率: {best_result_for_param.get('success_rate', 0):.2%}")
            
            self.save_param_results(param_name, param_results) 
        
        if self.default_params:
            if self.output_callback: self.output_callback("\n所有参数测试完成。正在保存最佳参数...")
            return self.save_best_params() 
        
        if self.output_callback: self.output_callback("性能测试未能确定最佳参数。", is_error=True)
        return None

    def save_param_results(self, param_name, results) -> str: 
        """保存单个参数的测试结果。返回文件路径。"""
        file_path = os.path.join(self.output_dir, f"param_test_{param_name}.json")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2)
            if self.output_callback: self.output_callback(f"参数 {self.param_names[param_name]} 的测试结果已保存到: {file_path}")
        except Exception as e:
            if self.output_callback: self.output_callback(f"保存参数 {param_name} 测试结果失败: {e}", is_error=True)
        
        self.all_param_results[param_name] = results
        return file_path
    
    def save_readable_results(self) -> str: 
        """将JSON测试结果转换为易读的TXT格式。返回文件路径。"""
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
        
        if self.output_callback: self.output_callback(f"测试结果已转换为易读格式，保存至: {output_file}")
        return output_file
    
    def save_best_params(self) -> tuple[dict, str, str]:
        """保存最佳参数组合。返回 (最佳参数字典, 可读结果文件路径, 优化配置路径)。"""
        best_params_file_path = os.path.join(self.output_dir, "best_params.json")
        try:
            with open(best_params_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.default_params, f, indent=2)
            if self.output_callback: self.output_callback(f"最佳参数已保存到: {best_params_file_path}")
        except Exception as e:
            if self.output_callback: self.output_callback(f"保存最佳参数文件失败: {e}", is_error=True)
        
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
        with open(config_path, 'w', encoding='utf-8') as f: # 这个 with 语句没有 try-except 包裹
            f.write(config_content)
        
        
        config_path = os.path.join(self.output_dir, "optimal_config.ini")
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(config_content)
            if self.output_callback: self.output_callback(f"优化后的配置文件已保存到: {config_path}")
        except Exception as e:
             if self.output_callback: self.output_callback(f"保存优化配置文件失败: {e}", is_error=True)
        
        # 生成易读的TXT格式测试结果
        readable_result_file_path = self.save_readable_results() 
        
        return self.default_params, readable_result_file_path, config_path

    def get_recommendations_text(self) -> tuple[str, str]: 
        """获取推荐参数的文本描述和优化配置文件的路径。"""
        recommendations_text = "DNS缓存工具性能测试完成，推荐参数设置:\n"
        recommendations_text += "="*60 + "\n"
        recommendations_text += f"每秒查询次数 (QueriesPerSecond): {self.default_params['QueriesPerSecond']}\n"
        recommendations_text += f"最大线程数 (MaxWorkers): {self.default_params['MaxWorkers']}\n"
        recommendations_text += f"DNS查询超时时间 (Timeout): {self.default_params['Timeout']}秒\n"
        recommendations_text += f"批处理大小 (BatchSize): {self.default_params['BatchSize']}个域名\n"
        recommendations_text += f"域名收集线程数 (CollectThreads): {self.default_params['CollectThreads']}\n"
        recommendations_text += "\n这些参数在当前系统和网络环境下应该具有最佳性能。\n"
        
        optimal_config_path = os.path.join(self.output_dir, "optimal_config.ini")
        return recommendations_text, optimal_config_path

class DNSCacheTool:
    def __init__(self, progress_callback=None, message_callback=None): # 添加了回调
        self.progress_callback = progress_callback
        self.message_callback = message_callback

        # 加载配置
        self.config = Config() # Config 类已被重构
        success, msg = self.config.load_config() # load_config 已被重构
        if self.message_callback: # 使用回调进行初始配置加载消息
            self.message_callback(msg)
        
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
            if self.message_callback: # 使用回调
                self.message_callback(f"解析URL时出错: {url}, 错误: {e}")
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
            if self.message_callback: # 使用回调
                self.message_callback(f"获取域名 {domain} 链接时出错: {e}")
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
            # 通过回调报告 socket_error
            result['error'] = str(socket_error) # 存储第一个错误
            if self.message_callback:
                self.message_callback(f"查询DNS时出错 (socket): {domain}, 错误: {socket_error}", is_error=True)
            try:
                resolver = dns.resolver.Resolver()
                resolver.timeout = self.config.getfloat('DNS', 'Timeout')
                resolver.lifetime = self.config.getfloat('DNS', 'Timeout')
                answers = resolver.resolve(domain, 'A')
                
                result['success'] = True # 如果dns.resolver成功，则标记为成功
                result['ip_addresses'] = [str(rdata) for rdata in answers] # 覆盖之前的空列表
                result['error'] = None # 清除之前的socket错误，因为dns.resolver成功了
            except Exception as dns_error:
                result['success'] = False # 确保如果dns_error发生，success为False
                # 如果socket_error已记录，则保留它；否则记录dns_error
                if not result['error']: # 只有当socket_error没有发生时，才记录dns_error
                    result['error'] = str(dns_error)
                if self.message_callback: # 使用回调
                    self.message_callback(f"查询DNS时出错 (dns.resolver): {domain}, 错误: {dns_error}")
        
        # 存储结果
        self.dns_results[domain] = result
        return result['success']
    
    def process_domain(self, domain):
        """处理单个域名的操作，用于多线程"""
        if domain in self.visited_domains:
            return
            
        self.visited_domains.add(domain)
        if self.progress_callback: # 使用 progress_callback
            self.progress_callback(f"正在处理域名: {domain}", len(self.collected_domains), self.target_count)
        
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
                    if self.message_callback: # 使用 message_callback
                        self.message_callback(f"已收集 {len(self.collected_domains)} 个域名")
                    self.save_domains_to_file(final_save=False) # save_domains_to_file 将被重构
        except Exception as e:
            if self.message_callback: # 使用 message_callback
                self.message_callback(f"处理域名 {domain} 时出错: {e}")

    def collect_domains(self, start_domain, only_subdomains=False) -> tuple[int, str | None]: # 添加了返回类型
        """从起始域名开始收集域名。返回 (收集到的域名数量, 最终保存文件路径)。"""
        self.only_subdomains = only_subdomains
        self.base_domain = start_domain
        if self.message_callback: # 使用 message_callback
            self.message_callback(f"开始从 {start_domain} 收集域名...")
        
        if only_subdomains:
            if self.message_callback: # 使用 message_callback
                self.message_callback(f"🔒 仅收集 {start_domain} 的子域名")
        
        self.visited_domains = set()
        self.domains_to_visit = {start_domain}
        self.collected_domains = set()
        self.dns_results = {}
        self.lock = threading.Lock()  # 添加线程锁
        
        # 重置当前文件名，让save_domains_to_file创建新文件名
        self.current_file = None
        
        # 创建线程池
        collect_threads = self.config.getint('Crawler', 'CollectThreads')
        if self.message_callback: # 使用 message_callback
            self.message_callback(f"🧵 使用 {collect_threads} 个线程进行域名收集")
        
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
        final_file_path = self.save_domains_to_file(final_save=True) # save_domains_to_file 将被重构以返回路径
        if self.message_callback: # 使用 message_callback
            self.message_callback(f"域名收集完成! 共收集了 {len(self.collected_domains)} 个域名")
        return len(self.collected_domains), final_file_path

    def batch_query_dns(self, file_path=None) -> tuple[int, int, dict | None]: # 添加了返回类型
        """批量查询DNS以加快缓存。返回 (成功计数, 总计数, DNS结果字典)。"""
        # load_domains_from_file 稍后将被重构
        domains_to_query = self.load_domains_from_file(file_path) if file_path else self.collected_domains
        
        if not domains_to_query:
            if self.message_callback: # 使用 message_callback
                self.message_callback("没有域名可供查询!")
            return 0, 0, None # 返回失败指示
        
        # 记录来源文件，用于生成更有描述性的导出文件名
        if file_path:
            self.current_source_file = file_path
        else:
            self.current_source_file = None
        
        # 清空之前的DNS结果
        self.dns_results = {}
        
        if self.message_callback: # 使用 message_callback
            self.message_callback(f"开始查询 {len(domains_to_query)} 个域名的DNS...")
            self.message_callback(f"注意: 查询速率限制为每秒最多{self.config.getint('DNS', 'QueriesPerSecond')}次查询")

        success_count = 0
        total_count = len(domains_to_query)
        
        # 使用限制线程数的线程池来控制并发查询
        # 确保 max_workers 至少为1，即使 total_count 为0（虽然在 domains_to_query 非空时不太可能）
        max_workers = min(self.config.getint('DNS', 'MaxWorkers'), total_count if total_count > 0 else 1)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            domains_list = list(domains_to_query)
            batch_size = self.config.getint('DNS', 'BatchSize')
            
            for i in range(0, len(domains_list), batch_size):
                batch = domains_list[i:i+batch_size]
                # query_dns 已被重构，将其结果存储在 self.dns_results 中
                # 并返回一个布尔值表示成功。
                future_results = [executor.submit(self.query_dns, domain) for domain in batch]
                
                batch_success_flags = [future.result() for future in future_results]
                batch_success_count = sum(1 for flag in batch_success_flags if flag)
                success_count += batch_success_count
                
                processed_count = i + len(batch)
                if self.progress_callback: # 使用 progress_callback
                    progress_percentage = min(100, int(processed_count / total_count * 100)) if total_count > 0 else 0
                    self.progress_callback(f"DNS查询进度: {progress_percentage}%", success_count, processed_count, total_count)
        
        if self.message_callback: # 使用 message_callback
            self.message_callback(f"DNS查询完成! 成功查询了 {success_count}/{total_count} 个域名")
        
        return success_count, total_count, self.dns_results # 返回结果

    # def ask_export_results(self): # 此方法已移除，CLI将处理此逻辑。
    #     """询问用户是否导出结果"""
    #     # ... (原始代码包含print和input) ...

    def export_results(self, format_type: str) -> str | None: # 添加了返回类型
        """导出DNS查询结果。返回导出的文件路径或None。"""
        if not self.dns_results:
            if self.message_callback: # 使用回调
                self.message_callback("没有结果可导出!")
            return None # 返回None
        
        timestamp = time.strftime("%Y%m%d%H%M")
        
        # 创建更有描述性的文件名
        filename_parts = []
        successful_domains = [domain for domain, result in self.dns_results.items() if result['success']]
        
        # 添加源文件或域名信息
        # 直接访问属性，并确保属性存在或提供默认值
        base_name_part = None
        if hasattr(self, 'base_domain') and self.base_domain: # 检查是否已设置 base_domain
            base_name_part = self.base_domain.replace('.', '_')
            filename_parts.append(base_name_part)
            if hasattr(self, 'only_subdomains') and self.only_subdomains: # 检查是否已设置 only_subdomains
                filename_parts.append("仅子域名")
        elif hasattr(self, 'current_source_file') and self.current_source_file: # 检查是否使用了源文件
            source_filename = os.path.basename(self.current_source_file)
            source_name = os.path.splitext(source_filename)[0]
            filename_parts.append(f"来源_{source_name}")
        
        # 添加成功查询数量信息
        if successful_domains: # 仅当有成功域名时添加
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
            if self.message_callback: # 使用回调
                self.message_callback(f"不支持的导出格式: {format_type}")
            return None # 返回None
        
        if self.message_callback: # 使用回调
            self.message_callback(f"结果已导出到: {export_file}")
        return export_file

    def save_domains_to_file(self, final_save=False) -> str | None: # 添加了返回类型
        """保存域名列表到文件。返回文件路径或None。
        
        参数:
            final_save (bool): 是否是最终保存，为True时会更新文件名中的域名数量
        """
        if not self.collected_domains:
            if self.message_callback: # 使用回调
                self.message_callback("没有域名可保存!")
            return None # 返回None
        
        # 如果是最终保存或者当前文件未创建，则创建/更新文件名
        if final_save or not self.current_file:
            timestamp = time.strftime("%Y%m%d%H%M")
            
            filename_parts_save = [] # 重命名以避免与外部作用域冲突（如果有）
            
            # 添加起始域名信息
            # 直接访问属性并检查其存在性
            if hasattr(self, 'base_domain') and self.base_domain:
                base_name = self.base_domain.replace('.', '_')
                filename_parts_save.append(base_name)
            
            # 添加是否只包含子域名信息
            if hasattr(self, 'only_subdomains') and self.only_subdomains:
                filename_parts_save.append("仅子域名")
            
            # 添加域名数量
            if self.collected_domains: # 仅当存在域名时添加长度
                filename_parts_save.append(f"{len(self.collected_domains)}个域名")
            
            # 合并所有部分
            descriptive_name = "-".join(filename_parts_save) if filename_parts_save else "collected_domains" # 默认名称
            
            # 完整文件名
            new_file = os.path.join(self.data_dir, f"{descriptive_name}_{timestamp}.json")
            
            if self.current_file and self.current_file != new_file and os.path.exists(self.current_file):
                if final_save:
                    try:
                        os.remove(self.current_file)
                        if self.message_callback: # 使用回调
                            self.message_callback(f"已删除旧文件: {self.current_file}")
                    except Exception as e:
                        if self.message_callback: # 使用回调
                            self.message_callback(f"删除旧文件时出错: {e}")
            
            self.current_file = new_file
        
        domains_data = list(self.collected_domains)
        
        try: # 为文件操作添加try-except
            with open(self.current_file, 'w', encoding='utf-8') as f:
                json.dump(domains_data, f, ensure_ascii=False, indent=2)
            if self.message_callback: # 使用回调
                self.message_callback(f"域名已保存到文件: {self.current_file}")
            return self.current_file
        except Exception as e:
            if self.message_callback:
                self.message_callback(f"保存域名文件时出错: {e}")
            return None

    def load_domains_from_file(self, file_path: str) -> set[str]: # 添加了类型提示
        """从文件加载域名列表。返回一个域名集合。"""
        try:
            # 记录来源文件
            self.current_source_file = file_path
            
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    # 加载JSON格式
                    data = json.load(f)
                    loaded_domains_count = 0 # 用于统一消息
                    
                    # 检查是否是直接的域名列表（新格式）
                    if isinstance(data, list):
                        domains = data
                        loaded_domains_count = len(domains)
                    # 检查是否是旧的复杂格式
                    elif isinstance(data, dict) and 'domains' in data:
                        domains = data['domains']
                        loaded_domains_count = len(domains)
                        # 加载子域名设置
                        if 'only_subdomains' in data and 'base_domain' in data:
                            self.only_subdomains = data['only_subdomains']
                            self.base_domain = data['base_domain']
                            if self.only_subdomains and self.base_domain and self.message_callback:
                                self.message_callback(f"该文件设置了基础域名: {self.base_domain}, 只收集子域名: {self.only_subdomains}")
                        # 如果文件包含DNS结果信息，也加载
                        if 'dns_results' in data:
                            self.dns_results = data['dns_results']
                            if self.message_callback:
                                self.message_callback(f"同时加载了 {len(self.dns_results)} 条旧DNS查询结果")
                    # 其他格式 (如果无法识别结构，则尝试解释为列表)
                    else:
                        if isinstance(data, list):
                            domains = data
                            loaded_domains_count = len(domains)
                        else: # 如果不是列表或无法识别的字典，则回退
                             domains = [] 
                             if self.message_callback:
                                self.message_callback(f"警告: 文件 {file_path} 不是预期的JSON列表或字典格式。")
                        
                except json.JSONDecodeError: # JSON特定错误
                    f.seek(0)  # 重置文件指针
                    if file_path.endswith('.csv'):
                        csv_reader = csv.reader(f)
                        try: 
                            next(csv_reader)  # 跳过表头
                        except StopIteration: # 空CSV
                             domains = []
                        else:
                            domains = []
                            for row in csv_reader:
                                if row and len(row) > 0:
                                    domains.append(row[0])
                        loaded_domains_count = len(domains)
                    else:
                        if self.message_callback:
                            self.message_callback(f"错误: 文件 {file_path} 不是有效的JSON或CSV文件。")
                        return set() 
                
                if self.message_callback:
                    self.message_callback(f"从文件 {file_path} 加载了 {loaded_domains_count} 个域名")

                self.collected_domains.update(set(domains)) # 更新收集到的域名，而不是替换
                return set(domains)
        except FileNotFoundError:
            if self.message_callback:
                self.message_callback(f"错误: 文件未找到 {file_path}")
            return set()
        except Exception as e:
            if self.message_callback:
                self.message_callback(f"加载域名文件时出错: {e}")
            return set()

    # def import_domains(self): # 此方法已移除，其逻辑将移至CLI特定函数
    #     """导入域名列表"""
    #     # ... (原始的CLI密集型代码在此) ...

    def get_available_files(self) -> list[str]: # 添加了返回类型
        """获取可用的域名文件列表。返回文件路径列表。"""
        if not os.path.exists(self.data_dir): # 处理不存在的data_dir
            try:
                os.makedirs(self.data_dir)
                if self.message_callback:
                    self.message_callback(f"数据目录 {self.data_dir} 不存在，已创建。")
                return [] # 返回空列表，因为目录刚创建
            except Exception as e:
                if self.message_callback:
                    self.message_callback(f"创建数据目录 {self.data_dir} 失败: {e}")
                return [] # 出错时返回空列表

        files = []
        try:
            for file_name in os.listdir(self.data_dir): # 将 'file' 重命名为 'file_name'
                if (file_name.startswith("domains_") and file_name.endswith(".json")) or \
                   (file_name.startswith("dns_results_") and (file_name.endswith(".json") or file_name.endswith(".csv"))):
                    files.append(os.path.join(self.data_dir, file_name))
        except Exception as e:
            if self.message_callback:
                self.message_callback(f"列出数据目录 {self.data_dir} 中的文件时出错: {e}")
        return files

    # def edit_config(self): # 已移除，CLI逻辑将在cli_edit_config中
    #     """编辑配置"""
    #     # ... (原始代码在此) ...

    # def edit_section(self, section): # 已移除，CLI逻辑将在cli_edit_section中
    #     """编辑特定配置部分"""
    #     # ... (原始代码在此) ...

    # def run_performance_test(self): # 已移除，CLI逻辑将在cli_run_performance_test中
    #     """运行性能测试，找出最佳参数配置"""
    #     # ... (原始代码在此) ...

# --- CLI特定函数 --- # 用于CLI交互的新区域

def cli_edit_config(tool: DNSCacheTool): # 从DNSCacheTool.edit_config改编的新函数
    """CLI: 编辑配置"""
    while True:
        print("\n" + "="*50)
            print("⚙️ 配置设置")
            print("="*50)
            
            sections = tool.config.config.sections() # 使用tool.config
            for i, section_key in enumerate(sections, 1): # 遍历键
                section_name = tool.config.get_name(section_key) # 获取翻译后的名称
                icon = ""
                if section_key == 'General': icon = "🔧"
                elif section_key == 'DNS': icon = "🌐"
                elif section_key == 'Crawler': icon = "🕸️"
                elif section_key == 'Export': icon = "📤"
                else: icon = "📝"
                print(f"{i}. {icon} {section_name if section_name != section_key else section_key}")
            print(f"{len(sections)+1}. 💾 保存并返回")
            
            try:
                choice = int(input("\n请选择要编辑的部分: "))
                
                if 1 <= choice <= len(sections):
                    section_key_selected = sections[choice-1] # 获取选定的键
                    cli_edit_section(tool, section_key_selected) # 调用新的CLI特定函数
                elif choice == len(sections)+1:
                    success, msg = tool.config.save_config() # 使用Config类的方法
                    if tool.message_callback: tool.message_callback(msg)
                    else: print(msg)
                    break
                else:
                    print("❌ 无效的选择!")
            except ValueError:
                print("❌ 请输入有效的数字!")

def cli_edit_section(tool: DNSCacheTool, section_key: str): # 从DNSCacheTool.edit_section改编的新函数
    """CLI: 编辑特定配置部分"""
    while True:
        section_name = tool.config.get_name(section_key)
        print(f"\n📝 编辑 {section_name if section_name != section_key else section_key} 配置")
        print("="*50)
        
        options = tool.config.config.options(section_key)
        for i, option_key in enumerate(options, 1): # 遍历键
            value = tool.config.get(section_key, option_key)
            option_chinese_name = tool.config.get_name(option_key)
            option_desc = tool.config.get_description(option_key)
            print(f"{i}. {option_chinese_name if option_chinese_name != option_key else option_key} = {value}")
            if option_desc:
                print(f"   - {option_desc}")
        print(f"{len(options)+1}. ⬅️ 返回上级菜单")
        
        try:
            choice = int(input("\n请选择要编辑的选项: "))
            
            if 1 <= choice <= len(options):
                option_key_selected = options[choice-1] # 获取选定的键
                option_chinese_name = tool.config.get_name(option_key_selected)
                current_value = tool.config.get(section_key, option_key_selected)
                option_desc = tool.config.get_description(option_key_selected)
                if option_desc:
                    print(f"描述: {option_desc}")
                
                prompt_name = option_chinese_name if option_chinese_name != option_key_selected else option_key_selected
                new_value = input(f"请输入新的 {prompt_name} 的值 (当前值: {current_value}): ")
                tool.config.set(section_key, option_key_selected, new_value) # 使用Config的方法
                msg = f"✅ 已更新 {prompt_name} = {new_value}"
                if tool.message_callback: tool.message_callback(msg)
                else: print(msg)
            elif choice == len(options)+1:
                break
            else:
                print("❌ 无效的选择!")
        except ValueError:
            print("❌ 请输入有效的数字!")

def cli_run_performance_test(tool: DNSCacheTool): # 从DNSCacheTool.run_performance_test改编的新函数
    """CLI: 运行性能测试，找出最佳参数配置"""
    print("\n" + "="*50)
    print("🚀 DNS缓存工具参数性能测试")
    print("="*50)
    
    use_current_domains = False
    test_file_for_perf_test = None 
    
    if tool.collected_domains:
        while True:
            choice = input(f"是否使用当前已收集的 {len(tool.collected_domains)} 个域名进行测试？(y/n): ")
            if choice.lower() in ['y', 'yes', '是', '是的']:
                use_current_domains = True
                
                temp_file_path = os.path.join(tool.data_dir, "temp_test_domains.json")
                try:
                    with open(temp_file_path, 'w', encoding='utf-8') as f:
                        json.dump(list(tool.collected_domains), f)
                    test_file_for_perf_test = temp_file_path
                    msg = f"已将当前域名保存到临时文件: {test_file_for_perf_test}"
                    if tool.message_callback: tool.message_callback(msg)
                    else: print(msg)
                except Exception as e:
                    msg = f"保存临时域名文件失败: {e}"
                    if tool.message_callback: tool.message_callback(msg)
                    else: print(msg)
                    test_file_for_perf_test = None 
                break
            elif choice.lower() in ['n', 'no', '否', '不']:
                break
            else:
                print("无效的输入，请输入 y 或 n")
    
    if not use_current_domains:
        available_files = tool.get_available_files() 
        if available_files:
            print("\n📂 可以使用的域名文件:")
            for i, file_path_available in enumerate(available_files, 1):
                print(f"{i}. {os.path.basename(file_path_available)}")
            print(f"{len(available_files)+1}. 使用默认测试域名")
            
            while True:
                try:
                    choice_idx = int(input("\n请选择要使用的文件 (输入序号): "))
                    if 1 <= choice_idx <= len(available_files):
                        test_file_for_perf_test = available_files[choice_idx-1]
                        print(f"选择了文件: {test_file_for_perf_test}")
                        break
                    elif choice_idx == len(available_files)+1:
                        print("将使用默认测试域名 (由DNSPerformanceTester内部加载)")
                        test_file_for_perf_test = None 
                        break
                    else:
                        print("无效的选择，请重试")
                except ValueError:
                    print("请输入有效的数字!")
        else:
            print("沒有可用的域名文件，将使用默认测试域名 (由DNSPerformanceTester内部加载)")
            test_file_for_perf_test = None

    tester = DNSPerformanceTester(test_file_for_perf_test, "test_results", tool.config)
    run_test_results = tester.run_tests() 
    
    if run_test_results:
        best_params, readable_results_path, optimal_config_path = run_test_results
        msg_best_params = f"\n最佳参数已计算并保存。"
        msg_opt_config = f"优化后的配置文件已保存到: {optimal_config_path}"
        msg_readable_results = f"易读格式的测试结果已保存到: {readable_results_path}"
        if tool.message_callback:
            tool.message_callback(msg_best_params)
            tool.message_callback(msg_opt_config)
            tool.message_callback(msg_readable_results)
        else:
            print(msg_best_params)
            print(msg_opt_config)
            print(msg_readable_results)

        recommendations_text, opt_config_path_from_getter = tester.get_recommendations_text()
        print("\n" + recommendations_text) 
        
        while True:
            user_input = input(f"\n是否将优化配置 {opt_config_path_from_getter} 复制到程序目录并重命名为 config.ini？(y/n): ")
            if user_input.lower() in ['y', 'yes', '是', '是的']:
                try:
                    import shutil
                    shutil.copy2(opt_config_path_from_getter, "config.ini")
                    msg_copy = f"已成功将配置文件复制为 config.ini"
                    if tool.message_callback: tool.message_callback(msg_copy)
                    else: print(msg_copy)
                    
                    loaded, load_msg = tool.config.load_config() 
                    if tool.message_callback: tool.message_callback(load_msg)
                    else: print(load_msg)
                    if loaded:
                        msg_reloaded = "配置已重新加载，新设置将在下次操作时生效"
                        if tool.message_callback: tool.message_callback(msg_reloaded)
                        else: print(msg_reloaded)
                except Exception as e:
                    msg_err_copy = f"复制配置文件时出错: {e}"
                    if tool.message_callback: tool.message_callback(msg_err_copy)
                    else: print(msg_err_copy)
                break
            elif user_input.lower() in ['n', 'no', '否', '不']:
                msg_not_applied = f"配置文件未应用，您可以稍后手动复制 {opt_config_path_from_getter} 到程序目录并重命名为 config.ini"
                if tool.message_callback: tool.message_callback(msg_not_applied)
                else: print(msg_not_applied)
                break
            else:
                print("无效的输入，请输入 y 或 n")
    else:
        if tool.message_callback:
            tool.message_callback("性能测试未能生成最佳参数。")
        else:
            print("性能测试未能生成最佳参数。")


    if use_current_domains and test_file_for_perf_test and os.path.exists(test_file_for_perf_test):
        try:
            os.remove(test_file_for_perf_test)
            msg_deleted_temp = f"已删除临时文件: {test_file_for_perf_test}"
            if tool.message_callback: tool.message_callback(msg_deleted_temp)
            else: print(msg_deleted_temp)
        except Exception as e:
            msg_err_delete_temp = f"删除临时文件时出错: {e}"
            if tool.message_callback: tool.message_callback(msg_err_delete_temp)
            else: print(msg_err_delete_temp)
    
    input("\n按Enter键返回主菜单...")


def cli_ask_export_results(tool: DNSCacheTool): # 从DNSCacheTool.ask_export_results改编的新函数
    """CLI: 询问用户是否导出结果"""
    if not tool.dns_results:
        msg = "没有可导出的结果!"
        if tool.message_callback: tool.message_callback(msg)
        else: print(msg)
        return
    
    while True:
        print("\n是否导出DNS查询结果?")
        print("1. 📊 导出为JSON格式")
        print("2. 📈 导出为CSV格式")
        print("3. ❌ 不导出")
        
        choice = input("\n请选择 (1-3): ")
        
        if choice == '1':
            tool.export_results('json') 
            break
        elif choice == '2':
            tool.export_results('csv') 
            break
        elif choice == '3':
            break
        else:
            print("无效的选择! 请重试。")

def cli_import_domains(tool: DNSCacheTool): # 从DNSCacheTool.import_domains改编的新函数
    """CLI: 导入域名列表"""
    print("\n📥 导入域名列表")
    print("支持的格式: JSON文件或CSV文件（第一列为域名）")
    
    file_path_to_import = input("请输入文件路径: ") 
    
    if not os.path.exists(file_path_to_import):
        msg = "❌ 文件不存在!"
        if tool.message_callback: tool.message_callback(msg)
        else: print(msg)
        return
    
    domains = tool.load_domains_from_file(file_path_to_import)
    if domains:
        msg_success_import = f"✅ 成功导入 {len(domains)} 个域名"
        if tool.message_callback: tool.message_callback(msg_success_import)
        else: print(msg_success_import)
        
        if input("\n是否对这些域名进行DNS查询? (y/n): ").lower() == 'y':
            success_count, total_count, dns_results_data = tool.batch_query_dns(file_path_to_import) 
            if dns_results_data: 
                 cli_ask_export_results(tool)


# --- 主CLI循环 ---
def main_cli(): # 将main重命名为main_cli
    # 用于CLI的简单进度和消息回调
    def cli_progress_handler(message, current, *args): 
        if not args:
             print(f"{message}: {current}")
        elif len(args) == 1: 
            total = args[0]
            print(f"{message} [{current}/{total}]")
        elif len(args) == 2: 
             processed_count, total_domains = args
             print(f"{message} (成功:{current}/已处理:{processed_count}/总数:{total_domains})")


    def cli_message_handler(message):
        print(message)

    tool = DNSCacheTool(progress_callback=cli_progress_handler, message_callback=cli_message_handler)
    
    
    while True:
        print("\n" + "="*50)
        print("🌐 DNS缓存工具 🚀 (CLI Mode)")
        print("="*50)
        print("1. 🔍 从新域名开始收集")
        print("2. 🔄 使用已有域名文件查询DNS")
        print("3. 📥 导入域名列表")
        print("4. 📤 导出上次查询结果")
        print("5. ⚙️ 配置设置")
        print("6. 🚀 运行性能测试")
        print("7. 👋 退出")
        
        cli_choice = input("\n请选择操作: ") 
        
        if cli_choice == '1':
            start_domain = input("请输入起始域名 (例如: example.com): ")
            if not start_domain:
                print("❌ 域名不能为空!")
                continue
            
            only_subdomains_choice = input(f"是否只收集 {start_domain} 的子域名? (y/n): ").lower()
            only_subdomains = only_subdomains_choice == 'y'
            
            tool.current_file = None 
            collected_count, final_file_path = tool.collect_domains(start_domain, only_subdomains)
            # 关于收集和保存的消息由回调处理
        
        elif cli_choice == '2':
            available_files = tool.get_available_files() 
            if not available_files:
                print("❌ 没有找到域名文件! 请先收集域名。")
                continue
            
            print("\n📂 可用的文件:")
            for i, file_path_option in enumerate(available_files, 1): 
                print(f"{i}. {os.path.basename(file_path_option)}")
            
            try:
                file_index = int(input("\n请选择文件 (输入序号): ")) - 1
                if 0 <= file_index < len(available_files):
                    selected_file = available_files[file_index]
                    success_count, total_count, dns_results_data = tool.batch_query_dns(selected_file)
                    if dns_results_data: 
                        cli_ask_export_results(tool) 
                else:
                    print("❌ 无效的选择!")
            except ValueError:
                print("❌ 请输入有效的序号!")
        
        elif cli_choice == '3':
            cli_import_domains(tool) 
        
        elif cli_choice == '4':
            cli_ask_export_results(tool) 
        
        elif cli_choice == '5':
            cli_edit_config(tool) 
        
        elif cli_choice == '6':
            cli_run_performance_test(tool) 
        
        elif cli_choice == '7':
            print("👋 感谢使用! 再见!")
            break
        
        else:
            print("❌ 无效的选择! 请重试。")

if __name__ == "__main__":
    main_cli() # 调用新的CLI主函数
