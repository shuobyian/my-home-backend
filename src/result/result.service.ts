import { Inject, Injectable, forwardRef } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { ReadItemDto } from 'src/item/dto/read-item-dto';
import { ItemService } from 'src/item/item.service';
import { Tool } from 'src/item/type/Tool';
import { Market } from 'src/market/entities/market.entity';
import { MarketService } from 'src/market/market.service';
import { ReadResultDto } from 'src/result/dto/read-item-dto';
import { Result } from 'src/result/entities/result.entity';
import { Material } from 'src/result/type/Material';
import { Page } from 'src/result/type/Page';
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
        ...this.parseResult(itemList, marketList, materials),
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
        ...this.parseResult(itemList, marketList, materials),
      };
    });

    return {
      results: this.parseResults(resultList, 1, itemList),
    };
  }

  parseResult(
    itemList: ReadItemDto[],
    marketList: Market[],
    items: Material[],
  ) {
    const materialList: Material[] = [];
    let middleMaterialList: Material[] = [];

    for (const item of items) {
      if (!item.base) {
        const included = materialList.findIndex((b) => b.name === item.name);
        if (included !== -1) {
          materialList[included].count += item.count;
        } else {
          materialList.push(item);
        }
      } else {
        middleMaterialList.push(item);
      }
    }

    while (middleMaterialList.length !== 0) {
      for (const item of itemList) {
        if (
          middleMaterialList.length > 0 &&
          middleMaterialList[0].name === item.name
        ) {
          for (const material of item.materials) {
            if (!middleMaterialList[0].base) {
              const included = materialList.findIndex(
                (b) => b.name === material.name,
              );
              if (included !== -1) {
                materialList[included].count +=
                  middleMaterialList[0].count * material.count;
              } else {
                materialList.push({
                  ...material,
                  count: middleMaterialList[0].count * material.count,
                });
              }
              middleMaterialList = middleMaterialList.slice(1);
            } else {
              middleMaterialList.push({
                ...material,
                count: middleMaterialList[0].count * material.count,
              });
            }
          }
          middleMaterialList = middleMaterialList.slice(1);
          break;
        }
      }
      if (middleMaterialList.length > 0 && !middleMaterialList[0].base) {
        const included = materialList.findIndex(
          (b) => b.name === middleMaterialList[0].name,
        );
        if (included !== -1) {
          materialList[included].count += middleMaterialList[0].count;
        } else {
          materialList.push(middleMaterialList[0]);
        }
        middleMaterialList = middleMaterialList.slice(1);
      }
    }
    const prices: number[] = [];
    for (const b of materialList) {
      for (const m of marketList) {
        if (b.name === m.name) {
          prices.push(b.count * m.price);
        }
      }
    }
    return {
      names: materialList.map((b) => b.name).toString(),
      counts: materialList.map((b) => b.count).toString(),
      prices: prices.toString(),
      totalPrice: prices.reduce((acc, cur) => (acc += cur), 0),
    };
  }

  parseResults(resultList: Result[], count: number, itemList: ReadItemDto[]) {
    return resultList.map((result) => {
      const { names, prices, counts, ...rest } = result;
      const nameList = names.split(',');
      const priceList = prices.split(',');
      const countList = counts.split(',');

      const rates = [1, 1.039, 1.156, 1.35, 1622];
      const rate = count < 5 ? rates[count - 1] : 1.613666 + 0.001555;

      const item = itemList.find((i) => i.name === result.name);

      return {
        ...rest,
        item: {
          ...item,
          materials: item.materials.map((material) => ({
            ...material,
            count: material.count * count,
          })),
        },
        craftingPrice: Math.floor(Number(result.craftingPrice) * count * rate),
        materials: Array.from({ length: nameList.length }, (_, index) => ({
          name: nameList[index],
          price: Number(priceList[index]) * count,
          count: Number(countList[index]) * count,
        })),
        totalPrice: result.totalPrice * count,
      };
    });
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
      content: this.parseResults(resultList, count, itemList),
    };
  }
}
