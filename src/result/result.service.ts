import {
  BadRequestException,
  Inject,
  Injectable,
  forwardRef,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { CreateItemDto } from 'src/item/dto/create-item-dto';
import { ItemService } from 'src/item/item.service';
import { Tool } from 'src/item/type/Tool';
import { Market } from 'src/market/entities/market.entity';
import { MarketService } from 'src/market/market.service';
import { ReadResultDto } from 'src/result/dto/read-item-dto';
import { Result } from 'src/result/entities/result.entity';
import { Page } from 'src/result/type/Page';
import { makeResult, parseResults } from 'src/result/util/UtilResult';
import { DataSource, Like, Repository } from 'typeorm';

@Injectable()
export class ResultService {
  constructor(
    private dataSource: DataSource,
    @InjectRepository(Result) private readonly result: Repository<Result>,
    @Inject(forwardRef(() => ItemService))
    private itemService: ItemService,
    @Inject(forwardRef(() => MarketService))
    private marketService: MarketService,
  ) {}

  async createAll() {
    const _resultList = await this.result.find();
    await Promise.all(_resultList.map((r) => this.result.delete({ id: r.id })));

    const itemList = await this.itemService.findAll();
    const marketList = await this.marketService.findAll();

    const resultList = itemList.map((item) => {
      const { materials, ...rest } = item;

      return {
        ...rest,
        ...makeResult(itemList, marketList, materials),
      };
    });

    return Promise.all(
      resultList.map((r) => this.result.save(this.result.create(r))),
    );
  }

  async calculator(marketList: Market[]) {
    const itemList = await this.itemService.findAll();

    const resultList: Result[] = itemList.map((item) => {
      const { materials, ...rest } = item;

      return {
        ...rest,
        createdAt: '',
        updatedAt: '',
        ...makeResult(itemList, marketList, materials),
      };
    });

    return {
      results: parseResults(resultList, 1, itemList),
    };
  }

  async uploadItems(itemList: CreateItemDto[]) {
    const _resultList = await this.result.find();
    const _itemList = itemList.filter(
      (item) => !_resultList.find(({ name }) => name === item.name),
    );

    if (_itemList.length < 1) {
      throw new BadRequestException('새로 추가된 아이템이 없습니다.');
    }

    const marketList = await this.marketService.findAll();

    const resultList = _itemList.map((item) => {
      const { materials, ...rest } = item;

      return {
        ...rest,
        ...makeResult(itemList, marketList, materials),
      };
    });

    const res = await Promise.all(
      resultList.map((r) => this.result.save(this.result.create(r))),
    );

    return parseResults(res, 1, itemList);
  }

  async findAllPage(
    page: number,
    size: number,
    name?: string,
    _count?: number,
    tool?: Tool,
  ): Promise<Page<ReadResultDto>> {
    const [resultList, totalElements] = await this.result.findAndCount({
      where: {
        name: name ? Like(`%${name}%`) : undefined,
        tool,
      },
      order: { level: 'ASC', name: 'ASC' },
      take: size,
      skip: page * size,
    });
    const count = _count ? _count : 1;

    const itemList = await Promise.all(
      resultList.map((result) => this.itemService.findOneByName(result.name)),
    );

    return {
      totalElements,
      content: parseResults(resultList, count, itemList),
    };
  }
}
