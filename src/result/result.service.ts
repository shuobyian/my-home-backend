/* eslint-disable @typescript-eslint/no-unused-vars */
import {
  BadRequestException,
  Inject,
  Injectable,
  forwardRef,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Market } from 'src/market/entities/market.entity';
import { MarketService } from 'src/market/market.service';
import { ProductService } from 'src/product/product.service';
import { Tool } from 'src/product/type/Tool';
import { ReadResultDto } from 'src/result/dto/read-result-dto';
import { Result } from 'src/result/entities/result.entity';
import { Page } from 'src/result/type/Page';
import { makeResult, parseResults } from 'src/result/util/UtilResult';
import { DataSource, Like, Repository } from 'typeorm';

@Injectable()
export class ResultService {
  constructor(
    private dataSource: DataSource,
    @InjectRepository(Result) private readonly result: Repository<Result>,
    @Inject(forwardRef(() => ProductService))
    private productService: ProductService,
    @Inject(forwardRef(() => MarketService))
    private marketService: MarketService,
  ) {}

  async createAll() {
    const _results = await this.result.find();
    const _products = await this.productService.findAll();
    const markets = await this.marketService.findAll();

    const products = _products.filter(
      (product) => !_results.find((result) => result.product_id === product.id),
    );

    if (products.length < 1) {
      throw new BadRequestException('추가할 결과가 없습니다.');
    }

    const results = products.map((product) => {
      const { materials, ...rest } = product;

      return {
        ...rest,
        product_id: product.id,
        ...makeResult(_products, markets, materials),
      };
    });

    return Promise.all(
      results.map((r) => this.result.save(this.result.create(r))),
    );
  }

  async calculator(markets: Market[]) {
    const _results = await this.result.find({ relations: { product: true } });
    const _products = await this.productService.findAll();

    const results: Result[] = _products.map((product) => {
      const { materials, craftingPrice, ...rest } = product;

      const result = _results.find(
        (_result) => _result.product_id === product.id,
      );

      if (!result) {
        throw new BadRequestException(
          `결과 정보가 없는 물품 (${product.name}) 입니다.`,
        );
      }

      return {
        ...result,
        ...rest,
        ...makeResult(_products, markets, materials),
      };
    });

    return {
      results: parseResults(results, 1, _products),
    };
  }

  async findAllPage(
    page: number,
    size: number,
    name?: string,
    _count?: number,
    tool?: Tool,
  ): Promise<Page<ReadResultDto>> {
    const [results, totalElements] = await this.result.findAndCount({
      relations: { product: true },
      where: { product: { name: name ? Like(`%${name}%`) : undefined, tool } },
      order: { product: { level: 'ASC', name: 'ASC' } },
      take: size,
      skip: page * size,
    });
    const count = _count ? _count : 1;

    const products = await Promise.all(
      results.map((result) => this.productService.findOne(result.product_id)),
    );

    return {
      totalElements,
      content: parseResults(results, count, products),
    };
  }
}
