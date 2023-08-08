import { Inject, Injectable, forwardRef } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { ItemService } from 'src/item/item.service';
import { MarketService } from 'src/market/market.service';
// import { CreateResultDto } from 'src/result/dto/create-result-dto';
import { Result } from 'src/result/entities/result.entity';
import { Material } from 'src/result/type/Material';
import { DataSource, Repository } from 'typeorm';

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
    const itemList = await this.itemService.findAll();
    const marketList = await this.marketService.findAll();

    const resultList = itemList.map((item) => {
      const basic: Material[] = [];
      let middle: Material[] = [];

      const { materials, ...rest } = item;
      for (const material of materials) {
        if (!material.base) {
          const isAlready = basic.findIndex((b) => b.name === material.name);
          if (isAlready !== -1) {
            basic[isAlready].count += material.count;
          } else {
            basic.push(material);
          }
        } else {
          middle.push(material);
        }
      }

      while (middle.length !== 0) {
        for (const item of itemList) {
          if (middle[0].name === item.name) {
            for (const material of item.materials) {
              if (!material.base) {
                const isAlready = basic.findIndex(
                  (b) => b.name === material.name,
                );
                if (isAlready !== -1) {
                  basic[isAlready].count += middle[0].count * material.count;
                } else {
                  basic.push({
                    ...material,
                    count: middle[0].count * material.count,
                  });
                }
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
          const isAlready = basic.findIndex((b) => b.name === middle[0].name);
          if (isAlready !== -1) {
            basic[isAlready].count += middle[0].count;
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
        ...rest,
        basic: basic.map((b) => b.name).toString(),
        counts: basic.map((b) => b.count).toString(),
        prices: prices.toString(),
        totalPrice: prices.reduce((acc, cur) => (acc += cur), 0),
      };
    });

    return Promise.all(
      resultList.map((r) => this.result.save(this.result.create(r))),
    );
  }

  // async create(createResultDto: CreateResultDto) {
  //   const { materials, ...rest } = createResultDto;
  //   for (const material of materials) {
  //     const prev = this.findOneByName(material.name);
  //     const item = await this.itemService.findOneByName(material.name);
  //   }

  //   return await this.result.save(this.result.create({ ...rest }));
  // }

  async findAll() {
    return await this.result.find();
  }

  async findOneByName(name?: string) {
    return await this.result.find({ where: { name } });
  }
}
