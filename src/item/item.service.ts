import { BadRequestException, Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { RawItemDto, ReadItemDto } from 'src/item/dto/read-item-dto';
import { Item } from 'src/item/entities/item.entity';
import { Page } from 'src/result/type/Page';
import { DataSource, Repository } from 'typeorm';

@Injectable()
export class ItemService {
  constructor(
    private dataSource: DataSource,
    @InjectRepository(Item) private readonly item: Repository<Item>,
  ) {}

  async login({ password }: { password: string }) {
    if (password !== process.env.PASSWORD) {
      throw new BadRequestException('비밀번호가 올바르지 않습니다.');
    }
    return '';
  }

  async findAll(): Promise<ReadItemDto[]> {
    const itemList = await this.item.find();
    return itemList.map((item) => ({
      id: item.id,
      ...this.parseItem(item),
    }));
  }

  async findAllPage(page: number, size: number): Promise<Page<ReadItemDto>> {
    const [itemList, totalElements] = await this.item.findAndCount({
      order: { id: 'ASC' },
      take: size,
      skip: page * size,
    });
    return {
      totalElements,
      content: itemList.map((item) => ({
        id: item.id,
        ...this.parseItem(item),
      })),
    };
  }

  async findOne(id: number): Promise<ReadItemDto> {
    const item = await this.item.findOne({ where: { id } });

    return {
      id: item.id,
      ...this.parseItem(item),
    };
  }

  async findOneByName(_name?: string): Promise<ReadItemDto> {
    const item = await this.item.findOne({ where: { name: _name } });

    return item
      ? {
          id: item.id,
          ...this.parseItem(item),
        }
      : undefined;
  }

  parseItem(item: RawItemDto) {
    const { name, level, craftingPrice, tool, ...rest } = item;
    const materials = [
      {
        name: rest.name1,
        base: rest.base1 === 1 ? true : false,
        count: rest.count1,
      },
      rest.name2 && {
        name: rest.name2,
        base: rest.base2 === 1 ? true : false,
        count: rest.count2,
      },
      rest.name3 && {
        name: rest.name3,
        base: rest.base3 === 1 ? true : false,
        count: rest.count3,
      },
      rest.name4 && {
        name: rest.name4,
        base: rest.base4 === 1 ? true : false,
        count: rest.count4,
      },
      rest.name5 && {
        name: rest.name5,
        base: rest.base5 === 1 ? true : false,
        count: rest.count5,
      },
    ].filter(Boolean);
    return {
      name,
      level,
      craftingPrice,
      tool,
      materials,
    };
  }
}
