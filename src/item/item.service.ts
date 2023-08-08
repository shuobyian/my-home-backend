import { BadRequestException, Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { CreateItemDto } from 'src/item/dto/create-item-dto';
import { Item } from 'src/item/entities/item.entity';
import { DataSource, Repository } from 'typeorm';

@Injectable()
export class ItemService {
  constructor(
    private dataSource: DataSource,
    @InjectRepository(Item) private readonly item: Repository<Item>,
  ) {}

  async create(createItemDto: CreateItemDto) {
    const { materials, ...rest } = createItemDto;

    if (this.item.findOne({ where: { name: createItemDto.name } })) {
      throw new BadRequestException('중복된 아이템입니다.');
    }

    return await this.item.save(
      this.item.create({
        ...rest,
        ...{
          material1: materials?.[0]?.name ?? '',
          base1: materials?.[0]?.base ? 1 : 0,
          count1: materials?.[0]?.count ?? 1,
          material2: materials?.[1]?.name,
          base2: materials?.[1]?.base ? 1 : 0,
          count2: materials?.[1]?.count,
          material3: materials?.[2]?.name,
          base3: materials?.[2]?.base ? 1 : 0,
          count3: materials?.[2]?.count,
          material4: materials?.[3]?.name,
          base4: materials?.[3]?.base ? 1 : 0,
          count4: materials?.[3]?.count,
          material5: materials?.[4]?.name,
          base5: materials?.[4]?.base ? 1 : 0,
          count5: materials?.[4]?.count,
        },
      }),
    );
  }

  async findAll() {
    const itemList = await this.item.find();
    return itemList.map((item) => {
      const { name, level, craftingPrice, ...rest } = item;
      const materials = [
        {
          name: rest.material1,
          base: rest.base1 === 1 ? true : false,
          count: rest.count1,
        },
        rest.material2 && {
          name: rest.material2,
          base: rest.base2 === 1 ? true : false,
          count: rest.count2,
        },
        rest.material3 && {
          name: rest.material3,
          base: rest.base3 === 1 ? true : false,
          count: rest.count3,
        },
        rest.material4 && {
          name: rest.material4,
          base: rest.base4 === 1 ? true : false,
          count: rest.count4,
        },
        rest.material5 && {
          name: rest.material5,
          base: rest.base5 === 1 ? true : false,
          count: rest.count5,
        },
      ].filter(Boolean);
      return {
        itemId: item.id,
        name,
        level,
        craftingPrice,
        materials,
      };
    });
  }

  async findOne(id: number) {
    return await this.item.findOne({ where: { id } });
  }
}
