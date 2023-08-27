import { Inject, Injectable, forwardRef } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { ItemService } from 'src/item/item.service';
import { MarketService } from 'src/market/market.service';
import { ReadResultDto } from 'src/result/dto/read-item-dto';
import { CreateResultDto } from 'src/result/dto/create-result-dto';
import { Result } from 'src/result/entities/result.entity';
import { Material } from 'src/result/type/Material';
import { Page } from 'src/result/type/Page';
import { DataSource, Like, Repository } from 'typeorm';
import { Market } from 'src/market/entities/market.entity';
import { ReadItemDto } from 'src/item/dto/read-item-dto';

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

  async create(createResultDto: CreateResultDto) {
    const itemList = await this.itemService.findAll();
    const marketList = await this.marketService.findAll();

    const { materials, ...rest } = createResultDto;

    return await this.result.save(
      this.result.create({
        ...rest,
        ...this.parseResult(itemList, marketList, materials),
      }),
    );
  }

  parseResult(
    itemList: ReadItemDto[],
    marketList: Market[],
    materials: Material[],
  ) {
    const basic: Material[] = [];
    let middle: Material[] = [];

    for (const material of materials) {
      if (!material.base) {
        const included = basic.findIndex((b) => b.name === material.name);
        if (included !== -1) {
          basic[included].count += material.count;
        } else {
          basic.push(material);
        }
      } else {
        middle.push(material);
      }
    }

    while (middle.length !== 0) {
      for (const item of itemList) {
        if (middle.length > 0 && middle[0].name === item.name) {
          for (const material of item.materials) {
            if (!middle[0].base) {
              const included = basic.findIndex((b) => b.name === material.name);
              if (included !== -1) {
                basic[included].count += middle[0].count * material.count;
              } else {
                basic.push({
                  ...material,
                  count: middle[0].count * material.count,
                });
              }
              middle = middle.slice(1);
            } else {
              middle.push({
                ...material,
                count: middle[0].count * material.count,
              });
            }
          }
          middle = middle.slice(1);
          break;
        }
      }
      if (middle.length > 0 && !middle[0].base) {
        const included = basic.findIndex((b) => b.name === middle[0].name);
        if (included !== -1) {
          basic[included].count += middle[0].count;
        } else {
          basic.push(middle[0]);
        }
        middle = middle.slice(1);
      }
    }
    const prices: number[] = [];
    for (const b of basic) {
      for (const m of marketList) {
        if (b.name === m.name) {
          prices.push(b.count * m.price);
        }
      }
    }
    return {
      basic: basic.map((b) => b.name).toString(),
      counts: basic.map((b) => b.count).toString(),
      prices: prices.toString(),
      totalPrice: prices.reduce((acc, cur) => (acc += cur), 0),
    };
  }

  async findAllPage(
    page: number,
    size: number,
    name?: string,
    _count?: number,
  ): Promise<Page<ReadResultDto>> {
    const [resultList, totalElements] = await this.result.findAndCount({
      where: { name: name ? Like(`%${name}%`) : undefined },
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
      content: resultList.map((result) => {
        const { basic, prices, counts, ...rest } = result;
        const nameList = basic.split(',');
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
          craftingPrice: Math.floor(
            Number(result.craftingPrice) * count * rate,
          ),
          basic: Array.from({ length: nameList.length }, (_, index) => ({
            name: nameList[index],
            price: Number(priceList[index]) * count,
            count: Number(countList[index]) * count,
          })),
          totalPrice: result.totalPrice * count,
        };
      }),
    };
  }
}
